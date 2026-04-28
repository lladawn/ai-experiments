"""
src/ingest/loader.py
Walk the Notion export directory and load raw documents.
Handles .md (with YAML front-matter), .html, and .csv files.
Returns a list of Document dicts ready for chunking.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Generator

import frontmatter
from bs4 import BeautifulSoup


@dataclass
class RawDocument:
    doc_id: str           # stable SHA-256 of (relative_path + mtime)
    source_path: str      # relative path inside raw_data dir
    title: str
    content: str          # raw text content
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RawDocument":
        return cls(**d)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stable_id(path: Path, raw_dir: Path) -> str:
    rel = str(path.relative_to(raw_dir))
    mtime = str(path.stat().st_mtime)
    return hashlib.sha256(f"{rel}:{mtime}".encode()).hexdigest()[:16]


def _load_markdown(path: Path, raw_dir: Path) -> RawDocument | None:
    try:
        post = frontmatter.load(str(path))
        content = post.content.strip()
        if not content:
            return None
        title = post.metadata.get("title") or path.stem.replace("-", " ").replace("_", " ")
        return RawDocument(
            doc_id=_stable_id(path, raw_dir),
            source_path=str(path.relative_to(raw_dir)),
            title=title,
            content=content,
            metadata={k: str(v) for k, v in post.metadata.items()},
        )
    except Exception as e:
        print(f"  [warn] skipping {path.name}: {e}")
        return None


def _load_html(path: Path, raw_dir: Path) -> RawDocument | None:
    try:
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
        # Remove script/style noise
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        title_tag = soup.find("title") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else path.stem
        content = soup.get_text(separator="\n", strip=True)
        if len(content) < 50:
            return None
        return RawDocument(
            doc_id=_stable_id(path, raw_dir),
            source_path=str(path.relative_to(raw_dir)),
            title=title,
            content=content,
        )
    except Exception as e:
        print(f"  [warn] skipping {path.name}: {e}")
        return None


def _load_csv(path: Path, raw_dir: Path) -> RawDocument | None:
    """
    Convert a Notion database CSV into a readable prose block.
    Each row becomes a 'Record: key=value, key=value ...' line.
    """
    try:
        rows = []
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter empty cells to keep text compact
                parts = [f"{k}={v}" for k, v in row.items() if v.strip()]
                if parts:
                    rows.append("Record: " + " | ".join(parts))
        if not rows:
            return None
        content = f"Database: {path.stem}\n\n" + "\n".join(rows)
        return RawDocument(
            doc_id=_stable_id(path, raw_dir),
            source_path=str(path.relative_to(raw_dir)),
            title=f"Database: {path.stem}",
            content=content,
            metadata={"type": "database"},
        )
    except Exception as e:
        print(f"  [warn] skipping {path.name}: {e}")
        return None


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _processed_ids(processed_dir: Path) -> set[str]:
    """Return set of doc_ids that have already been processed."""
    ids: set[str] = set()
    index = processed_dir / "index.json"
    if index.exists():
        ids = set(json.loads(index.read_text()))
    return ids


def _save_index(processed_dir: Path, ids: set[str]) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    (processed_dir / "index.json").write_text(json.dumps(sorted(ids)))


# ── Public API ────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".md", ".html", ".htm", ".csv"}


def load_documents(
    raw_dir: str | Path,
    processed_dir: str | Path,
    force_reload: bool = False,
) -> Generator[RawDocument, None, None]:
    """
    Walk raw_dir and yield RawDocuments not yet in processed_dir.
    Pass force_reload=True to re-process everything.
    """
    raw_dir = Path(raw_dir)
    processed_dir = Path(processed_dir)

    if not raw_dir.exists():
        raise FileNotFoundError(f"raw_data directory not found: {raw_dir}")

    known_ids = set() if force_reload else _processed_ids(processed_dir)
    new_ids: set[str] = set()

    all_files = [p for p in raw_dir.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    print(f"Found {len(all_files)} files in {raw_dir}")

    for path in sorted(all_files):
        doc_id = _stable_id(path, raw_dir)
        if doc_id in known_ids:
            continue  # already ingested

        ext = path.suffix.lower()
        doc: RawDocument | None = None

        if ext == ".md":
            doc = _load_markdown(path, raw_dir)
        elif ext in {".html", ".htm"}:
            doc = _load_html(path, raw_dir)
        elif ext == ".csv":
            doc = _load_csv(path, raw_dir)

        if doc:
            new_ids.add(doc_id)
            yield doc

    # Persist updated index
    _save_index(processed_dir, known_ids | new_ids)
    print(f"Loaded {len(new_ids)} new documents ({len(known_ids)} already cached)")
