#!/usr/bin/env python3
"""
scripts/run_ingest.py
Full ingestion pipeline:
  1. Load documents from data/raw/
  2. Split into chunks
  3. Embed chunks with Ollama
  4. Store embeddings in ChromaDB
  5. Extract structured events with LLM
  6. Store events in SQLite

Run from project root:
    python scripts/run_ingest.py [--force] [--skip-extraction] [--extract-only]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.extract.extractor import extract_events
from src.ingest.embedder import embed_chunks
from src.ingest.loader import load_documents
from src.ingest.splitter import split_documents
from src.store.event_store import EventStore
from src.store.vector_store import VectorStore


def main(
    force: bool = False, skip_extraction: bool = False, extract_only: bool = False
) -> None:
    cfg = get_config()
    t0 = time.time()

    print("=" * 60)
    print("Notion Knowledge Assistant — Ingest Pipeline")
    print("=" * 60)

    # If extract-only was requested, skip embedding/vector steps and
    # run extraction over all pages (force load everything).
    if extract_only:
        print("\n[EXTRACT-ONLY] Loading all documents for extraction...")
        docs_all = list(
            load_documents(
                raw_dir=cfg.paths.raw_data,
                processed_dir=cfg.paths.processed,
                force_reload=True,
            )
        )
        if not docs_all:
            print("  No documents found to extract from.")
            return

        print(
            f"\n[EXTRACT-ONLY] Extracting events from {len(docs_all)} pages (model: {cfg.models.llm})..."
        )
        events = extract_events(
            docs_all,
            model=cfg.models.llm,
            max_events_per_page=cfg.extraction.max_events_per_page,
        )
        event_store = EventStore(cfg.paths.sqlite_db)
        if force:
            event_store.clear()
        count = event_store.insert_events(events)
        print(f"  → SQLite now contains {count:,} events")
        elapsed = time.time() - t0
        print(f"\n✓ Extract-only complete in {elapsed:.1f}s")
        print("  Launch UI: streamlit run src/ui/app.py")
        return

    # ── Step 1: Load (new documents only unless --force) ─────────────────────────
    print("\n[1/4] Loading documents (new only)...")
    new_docs = list(
        load_documents(
            raw_dir=cfg.paths.raw_data,
            processed_dir=cfg.paths.processed,
            force_reload=force,
        )
    )

    if not new_docs:
        # No new documents. If the user also asked to skip extraction, we can stop;
        # otherwise we want to run extraction over the full set of documents (cached).
        print("  No new documents found. Use --force to re-process everything.")
        if skip_extraction:
            print("  Skipping extraction (no new docs and --skip-extraction set).")
            return

        # Load all documents for extraction (do not modify processed index here).
        print("  Running extraction on all cached documents...")
        docs_for_extraction = list(
            load_documents(
                raw_dir=cfg.paths.raw_data,
                processed_dir=cfg.paths.processed,
                force_reload=True,
            )
        )
        # Proceed directly to extraction (skip embedding/upsert steps)
        print(
            f"\n[4/4] Extracting events from {len(docs_for_extraction)} pages (model: {cfg.models.llm})..."
        )
        events = extract_events(
            docs_for_extraction,
            model=cfg.models.llm,
            max_events_per_page=cfg.extraction.max_events_per_page,
        )
        event_store = EventStore(cfg.paths.sqlite_db)
        if force:
            event_store.clear()
        count = event_store.insert_events(events)
        print(f"  → SQLite now contains {count:,} events")
        elapsed = time.time() - t0
        print(f"\n✓ Ingest complete in {elapsed:.1f}s")
        print("  Launch UI: streamlit run src/ui/app.py")
        return

    # ── Step 2: Split ─────────────────────────────────────────────────────────
    print(f"\n[2/4] Splitting {len(new_docs)} new documents into chunks...")
    chunks = split_documents(
        new_docs,
        chunk_size=cfg.chunking.chunk_size,
        chunk_overlap=cfg.chunking.chunk_overlap,
    )
    print(f"  → {len(chunks)} chunks created")

    # ── Step 3: Embed + store in ChromaDB ─────────────────────────────────────
    print(f"\n[3/4] Embedding {len(chunks)} chunks (model: {cfg.models.embeddings})...")
    embeddings = embed_chunks(chunks, model=cfg.models.embeddings)

    vector_store = VectorStore(cfg.paths.chroma_db)
    total = vector_store.upsert(chunks, embeddings)
    print(f"  → ChromaDB now contains {total:,} chunks")

    # ── Step 4: Extract events ────────────────────────────────────────────────
    if not skip_extraction:
        print(f"\n[4/4] Extracting events (model: {cfg.models.llm})...")
        # Extract only from the (new) docs processed in this run. If you want extraction over all docs,
        # use --extract-only or run without --skip-extraction when there are no new docs.
        events = extract_events(
            new_docs,
            model=cfg.models.llm,
            max_events_per_page=cfg.extraction.max_events_per_page,
        )

        event_store = EventStore(cfg.paths.sqlite_db)
        if force:
            event_store.clear()
        count = event_store.insert_events(events)
        print(f"  → SQLite now contains {count:,} events")
    else:
        print("\n[4/4] Skipping event extraction (--skip-extraction flag set)")

    elapsed = time.time() - t0
    print(f"\n✓ Ingest complete in {elapsed:.1f}s")
    print("  Launch UI: streamlit run src/ui/app.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest Notion export into local RAG system"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process all files even if already ingested",
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip LLM event extraction (embedding only)",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Run only the LLM extraction step over all raw pages (no embedding/upsert)",
    )
    args = parser.parse_args()
    main(
        force=args.force,
        skip_extraction=args.skip_extraction,
        extract_only=args.extract_only,
    )
