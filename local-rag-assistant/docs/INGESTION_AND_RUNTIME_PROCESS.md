# Notion RAG Assistant — Ingestion & Runtime Process

This document describes the end-to-end process implemented in this repository, where Notion export files are transformed into an indexed RAG system and structured events database.

## Overview
- Orchestration script: `scripts/run_ingest.py`
- Load raw files: `src/ingest/loader.py`
- Split into chunks: `src/ingest/splitter.py`
- Embed chunks: `src/ingest/embedder.py` (uses Ollama)
- Store embeddings: `src/store/vector_store.py` (ChromaDB)
- Extract structured events: `src/extract/extractor.py` (+ `src/extract/schema.py`)
- Store events: `src/store/event_store.py` (SQLite + DuckDB for analytics)
- UI: `src/ui/app.py` (Streamlit)

## Configuration
Configuration is read by `src/config.py` from `config.yaml` (or `config.example.yaml` by default). Important keys:
- `paths.raw_data` — directory with Notion export (default `data/raw`).
- `paths.processed` — processed cache (default `data/processed`).
- `paths.chroma_db` — ChromaDB persistent path (default `db/chroma`).
- `paths.sqlite_db` — SQLite events DB (default `db/events.db`).
- `models.llm` — LLM model for chat/extraction.
- `models.embeddings` — embedding model.

## Data flow (step-by-step)

1. Start pipeline
   - Run `python scripts/run_ingest.py` from the project root.
   - Optional flags: `--force` (reprocess all files), `--skip-extraction` (do not run LLM extraction).

2. Loading raw files
   - `src/ingest/loader.py` scans `data/raw` recursively for `.md`, `.html`, `.csv`.
   - Each file is parsed into a `RawDocument` with: `doc_id`, `source_path`, `title`, `content`, `metadata`.
   - The loader reads `data/processed/index.json` to obtain known `doc_id`s and yields only new documents by default.
   - At the end it updates `index.json` to include newly processed IDs.

3. Splitting
   - `src/ingest/splitter.py` uses a text splitter to break each document into overlapping chunks.
   - Each `Chunk` keeps provenance (doc id, source path, title) so results can cite the source.

4. Embeddings
   - `src/ingest/embedder.py` validates Ollama availability and the presence of the embedding model.
   - Batches chunk texts and calls `ollama.embed` to get vector embeddings.

5. Storing vectors
   - `src/store/vector_store.py` upserts chunk `ids`, `documents`, `metadatas`, and `embeddings` into a persistent Chroma collection `notion_chunks`.
   - `VectorStore.search()` allows retrieval by embedding similarity.

6. Extracting structured events
   - `src/extract/extractor.py` builds a structured extraction prompt and calls `ollama.chat` to request a JSON array of events per page.
   - Responses are parsed (strip fences, find outermost JSON array), then each row is validated into an `Event` via `src/extract/schema.py`.
   - Valid events are returned as a flat list.

7. Storing events
   - `src/store/event_store.py` writes validated events into SQLite table `events`.
   - `Analytics` uses DuckDB to run read-only SQL analytics over the same SQLite file for dashboards.

8. UI (Streamlit)
   - `src/ui/app.py` loads resources (vector store, event store, analytics, retriever).
   - Chat tab: retrieve relevant chunks for a user prompt, call generator to stream an LLM answer, display citations.
   - Timeline tab: show analytics charts and allow generation of AI summaries.

## Important files and locations
- `scripts/run_ingest.py` — run the pipeline.
- `src/ingest/loader.py` — file parsing and processed index logic (`data/processed/index.json`).
- `src/ingest/splitter.py` — chunk creation.
- `src/ingest/embedder.py` — embedding calls to Ollama.
- `src/store/vector_store.py` — ChromaDB persistence (`db/chroma`).
- `src/extract/extractor.py` — chat-based event extraction.
- `src/extract/schema.py` — Pydantic `Event` validation.
- `src/store/event_store.py` — SQLite `db/events.db` + DuckDB analytics.
- `src/ui/app.py` — Streamlit UI.

## Troubleshooting tips
- Extraction looks stuck (tqdm stays at 0%):
  - Verify Ollama is running: `ollama list` and `ollama serve`.
  - Confirm the exact model name in `config.yaml` matches the name in `ollama list`.
  - From Python, test:
    - `python -c "import ollama; print(ollama.list())"`
    - `python -c "import ollama; r=ollama.chat(model='<model_name>', messages=[{'role':'system','content':'You are a test.'},{'role':'user','content':'Say hi'}]); print(r)"`
  - Run extractor on a single document:
    - `python -c "from src.ingest.loader import load_documents; from src.extract.extractor import extract_events; docs=list(load_documents('data/raw','data/processed',force_reload=True)); print('docs', len(docs)); print(extract_events([docs[0]]))"`
  - If the model is missing: `ollama pull <model_name>` (use exact model name).
- Forcing re-run:
  - Use `--force` with `scripts/run_ingest.py`, or remove `data/processed/index.json` to cause all docs to be reprocessed.
- If you want to extract over all pages without re-embedding:
  - The current `run_ingest.py` supports `--skip-extraction` but does not have an `--extract-only` flag; you can re-run with `--force` or manually run `extract_events(...)` in a short script.

## Notes & future improvements
- Add an `--extract-only` mode to `scripts/run_ingest.py` (convenience for re-running extraction only).
- Add a `_check_ollama` model check before `ollama.chat` to fail fast if the model isn't present.
- Add more granular logging around LLM calls to surface which documents cause slow responses.
- Convert extraction to batched or streamed processing to avoid a long single run for many pages.

## Quick commands
- Full ingest: `python scripts/run_ingest.py`
- Reprocess everything: `python scripts/run_ingest.py --force`
- Streamlit UI: `streamlit run src/ui/app.py`
- List local Ollama models: `ollama list`
- Pull model: `ollama pull <model_name>`

---

End of document.
