# Notion Knowledge Assistant

A private, local-first RAG system to chat with your Notion export, extract structured timelines, and reflect on your work — no cloud APIs, no costs.

## Stack

| Layer | Tool |
|---|---|
| LLM | `mistral-small3.2` via Ollama (Q4_K_M, 24B) |
| Embeddings | `mxbai-embed-large` via Ollama |
| Vector DB | ChromaDB (persistent, local) |
| Structured store | SQLite (writes) + DuckDB (analytics) |
| UI | Streamlit |

## Requirements

- macOS (Apple Silicon) — tested on M3 Pro 36GB
- Python 3.12 (required — do not use 3.13/3.14, hnswlib won't build)
- [Ollama](https://ollama.com) installed and running

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/notion-assistant.git
cd notion-assistant

# 2. Create a Python 3.12 virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the required Ollama models
ollama pull mistral-small3.2
ollama pull mxbai-embed-large

# 5. Copy the example config and set your data path
cp config.example.yaml config.yaml
# Edit config.yaml to point to your Notion export folder
```

## Adding your Notion data

Export your Notion workspace:
- Go to **Settings → Export content → Export all workspace content**
- Format: **Markdown & CSV**
- Unzip the export into `data/raw/`

```
data/
└── raw/
    ├── My Project/
    │   ├── Page Title.md
    │   └── Database.csv
    └── Journal/
        └── 2024-01-15.md
```

> `data/` is git-ignored — your notes never leave your machine.

## Usage

```bash
# Step 1: Ingest (parse → embed → store in ChromaDB + SQLite)
python scripts/run_ingest.py

# Step 2: Launch the chat UI
streamlit run src/ui/app.py

# Optional: Run analytics only (monthly timeline)
python scripts/run_analytics.py
```

## Project structure

```
notion-assistant/
├── data/               # git-ignored — your Notion export goes here
│   ├── raw/
│   └── processed/
├── db/                 # git-ignored — vector store and SQLite DB
│   ├── chroma/
│   └── events.db
├── src/
│   ├── ingest/         # load, chunk, embed
│   ├── extract/        # LLM-based event extraction
│   ├── store/          # ChromaDB + SQLite helpers
│   ├── query/          # retriever, generator, analytics
│   └── ui/             # Streamlit app
├── scripts/            # one-shot runner scripts
├── tests/              # unit tests
├── config.yaml         # your local config (git-ignored)
├── config.example.yaml # template committed to git
└── requirements.txt
```

## Notes

- Re-running `run_ingest.py` is idempotent — already-processed files are skipped
- The extractor uses Pydantic validation; malformed LLM rows are silently dropped
- All data stays local: no telemetry, no cloud calls
