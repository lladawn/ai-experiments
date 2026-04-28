"""
src/extract/extractor.py
Use the local LLM to extract structured Event rows from note text.
Output is validated with Pydantic; invalid rows are dropped, not raised.

This implementation adds:
- Per-page timeout using ThreadPoolExecutor (default 120s).
- Progress tracking persisted to a JSON file so interrupted runs can resume.
- A pre-flight short-content skip: pages with stripped content < 100 chars are skipped proactively.
- Summary printed at the end with counts for attempted, timed out, zero-event pages and total events.

Notes:
- The 3-attempt retry/backoff, JSON parsing, and Pydantic validation logic are preserved.
- Timed-out pages and short pages are recorded in the progress file so future runs skip them.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
from pathlib import Path
from typing import Sequence

import ollama
from tqdm import tqdm

from src.config import get_config
from src.extract.schema import Event
from src.ingest.loader import RawDocument

# ── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a structured data extractor. Your ONLY job is to extract events from personal notes and return them as a JSON array.

Rules:
- Respond with ONLY a valid JSON array. No explanation, no markdown, no backticks.
- Each item must follow this exact schema:
  {
    "date": "YYYY-MM-DD or YYYY-MM or null",
    "project": "project name or null",
    "topic": "topic/subject or null",
    "action": "one concise sentence describing what was done",
    "insight": "one concise sentence about what was learned, or null",
    "source_page": "PLACEHOLDER"
  }
- If no events can be extracted, return an empty array: []
- Do not invent dates or facts not present in the note.
- Keep action and insight under 150 characters each."""

_USER_TEMPLATE = """Extract events from this note. Replace "PLACEHOLDER" in source_page with "{source_page}".

--- NOTE START ---
{content}
--- NOTE END ---

Respond with JSON array only."""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_ollama(model: str) -> None:
    """Raise a clear error if Ollama is not running or model is missing."""
    try:
        tags = ollama.list()
        available = [m.model for m in tags.models]
        if not any(model in name for name in available):
            raise RuntimeError(
                f"Model '{model}' not found in Ollama.\n"
                f"Run: ollama pull {model}\n"
                f"Available: {available}"
            )
    except Exception as e:
        if "Connection refused" in str(e) or "connect" in str(e).lower():
            raise RuntimeError(
                "Ollama is not running. Start it with: ollama serve"
            ) from e
        raise


def _parse_json_response(raw: str) -> list[dict]:
    """Strip markdown fences and parse JSON array from LLM output."""
    # Remove common fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("` \n")
    # Find the outermost [ ... ]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return []


def _validate_rows(rows: list[dict], source_page: str) -> list[Event]:
    """Validate raw dicts into Event objects. Drop invalid rows silently."""
    events: list[Event] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row["source_page"] = source_page  # always override with ground truth
        try:
            events.append(Event(**row))
        except Exception:
            pass  # silently drop malformed rows
    return events


# ── Public API ────────────────────────────────────────────────────────────────


def extract_events(
    documents: Sequence[RawDocument],
    # model: str = "mistral-small3.2:latest",
    model: str = get_config().models.llm,
    max_events_per_page: int = 10,
    timeout_seconds: int = 120,
    progress_file: str = "data/processed/extraction_progress.json",
) -> list[Event]:
    """
    Extract structured events from a list of RawDocuments.
    Returns a flat list of validated Event objects.

    Parameters:
    - documents: sequence of RawDocument to process
    - model: Ollama model string
    - max_events_per_page: cap events per page
    - timeout_seconds: per-page maximum time for the LLM call (default 120)
    - progress_file: path to JSON file that stores processed source_path entries
    """
    # Fail fast if Ollama or model isn't available
    _check_ollama(model)

    all_events: list[Event] = []

    progress_path = Path(progress_file)
    processed_paths: set[str] = set()
    if progress_path.exists():
        try:
            loaded = json.loads(progress_path.read_text(encoding="utf-8") or "[]")
            if isinstance(loaded, list):
                processed_paths = set(str(x) for x in loaded)
        except Exception:
            # ignore malformed progress file and start fresh
            processed_paths = set()

    # Build list of docs to process (skip those already in progress file)
    docs_to_process = [d for d in documents if d.source_path not in processed_paths]

    if not docs_to_process:
        print("No pages to extract (all pages already in progress file).")
        print(f"Progress file: {progress_path}")
        return []

    total_pages_attempted = len(docs_to_process)
    timed_out_pages: list[str] = []
    zero_event_pages: list[str] = []
    skipped_short_pages: list[str] = []

    # Iterate serially over pages. Each page's LLM call runs in its own short-lived
    # thread so we can impose a timeout without blocking the rest of the run.
    for doc in tqdm(docs_to_process, desc="Extracting events", unit="page"):
        # Truncate very long pages to keep within context window
        content = doc.content[:4000]

        # Pre-flight short-content skip: only skip if stripped content is under threshold
        if len(content.strip()) < 100:
            print(f"[skip] {doc.source_path} too short (<100 chars)")
            skipped_short_pages.append(doc.source_path)
            # mark as processed so we don't retry it on next run
            try:
                processed_paths.add(doc.source_path)
                progress_path.parent.mkdir(parents=True, exist_ok=True)
                progress_path.write_text(
                    json.dumps(sorted(processed_paths)), encoding="utf-8"
                )
            except Exception as e:
                print(f"  [warn] failed to write progress file {progress_path}: {e}")
            continue

        prompt = _USER_TEMPLATE.format(
            source_page=doc.source_path,
            content=content,
        )

        raw_response = ""
        timed_out = False

        # Preserve the original 3-attempt retry logic and backoff
        for attempt in range(3):
            try:
                print(
                    f"  [debug] Extracting {doc.source_path} (attempt {attempt + 1}/3, model={model})"
                )

                # Create a per-page executor. We do not use a persistent shared executor
                # because we want strong isolation and the ability to shutdown per-call
                # without waiting for lingering background threads.
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(
                    ollama.chat,
                    model=model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    options={"temperature": 0.1},  # low temp for structured output
                )
                try:
                    response = future.result(timeout=timeout_seconds)
                    raw_response = (
                        getattr(response, "message", None)
                        and response.message.content
                        or str(response)
                    )
                    print(
                        f"  [debug] Received response for {doc.source_path} (len={len(raw_response)})"
                    )
                    # Best-effort cleanup; do not wait for background thread if it lingers.
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    try:
                        executor.shutdown(wait=False)
                    except Exception:
                        pass
                    break
                except concurrent.futures.TimeoutError:
                    # Timeout: skip this page, record it, and do not raise.
                    print(
                        f"[skip] {doc.source_path} timed out after {timeout_seconds}s"
                    )
                    timed_out = True
                    # Best-effort attempt to cancel and release executor resources.
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    try:
                        executor.shutdown(wait=False)
                    except Exception:
                        pass
                    break  # skip this page and move on

            except Exception as e:
                print(
                    f"  [warn] extraction attempt {attempt + 1} failed for {doc.source_path}: {e}"
                )
                if attempt == 2:
                    print(f"  [warn] giving up on {doc.source_path} after 3 attempts")
                    raw_response = ""
                    # continue to next doc
                else:
                    # backoff before retry
                    time.sleep(1.5 * (attempt + 1))

        # Parse & validate as before
        rows = _parse_json_response(raw_response)[:max_events_per_page]
        events = _validate_rows(rows, doc.source_path)
        all_events.extend(events)

        # Track timed out pages and zero-event pages (zero-event only for non-timeout run)
        if timed_out:
            timed_out_pages.append(doc.source_path)
        else:
            if not events:
                zero_event_pages.append(doc.source_path)

        # Persist progress after processing (or skipping) this page
        try:
            processed_paths.add(doc.source_path)
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            progress_path.write_text(
                json.dumps(sorted(processed_paths)), encoding="utf-8"
            )
        except Exception as e:
            print(f"  [warn] failed to write progress file {progress_path}: {e}")

    # Summary
    print("\nExtraction summary:")
    print(f"  Total pages attempted: {total_pages_attempted}")
    print(f"  Pages timed out: {len(timed_out_pages)}")
    if timed_out_pages:
        for p in timed_out_pages:
            print(f"    - {p}")
    print(f"  Pages with 0 events: {len(zero_event_pages)}")
    if zero_event_pages:
        for p in zero_event_pages:
            print(f"    - {p}")
    print(f"  Pages skipped (too short): {len(skipped_short_pages)}")
    if skipped_short_pages:
        for p in skipped_short_pages:
            print(f"    - {p}")
    print(f"  Total valid events extracted: {len(all_events)}")

    return all_events
