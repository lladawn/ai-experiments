# Daily Digest Agent

A local AI agent that fetches content from your favourite sources every morning, scores each item for relevance using a local LLM, and delivers a clean Markdown digest — no cloud required.

## Features

- Fetches from RSS feeds, Hacker News, Reddit (no API keys needed)
- Scores and summarises items using **Ollama** (local, free) or **Groq** (free API tier)
- Deduplicates across days — you never see the same story twice
- Outputs a clean Markdown digest with relevance scores and tags
- Fully configurable via `config.yaml`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama (for local LLM)

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

Or use **Groq** (free, fast, no GPU needed):
```bash
export GROQ_API_KEY=your_key_here
# then set provider: "groq" and groq_model in config.yaml
```

### 3. Configure your digest

Edit `config.yaml`:
- Set your **interests** (used for LLM relevance scoring)
- Enable/disable sources (RSS feeds, HN, Reddit)
- Set your preferred **output** (terminal, file, email)

### 4. Run

```bash
python main.py
```

### 5. Schedule it (optional)

```bash
# Run every day at 7am
crontab -e
# add:
0 7 * * * cd /path/to/daily-digest-agent && python main.py
```

## Project structure

```
daily-digest-agent/
├── config.yaml          # your interests, sources, schedule
├── main.py              # orchestrator — run this
├── fetchers/
│   ├── rss.py           # RSS/Atom feeds via feedparser
│   ├── hackernews.py    # HN top stories via Firebase API
│   └── reddit.py        # Reddit hot posts via JSON API
├── agent/
│   ├── models.py        # DigestItem dataclass
│   ├── filter.py        # dedup + keyword pre-scoring
│   └── summarizer.py    # LLM scoring + summarisation
├── outputs/
│   └── markdown.py      # Markdown renderer
├── digests/             # output files land here
└── data/
    └── seen_urls.json   # dedup memory
```

## How it works

```
cron / manual run
      │
      ▼
Fetch sources (parallel)
  RSS + HN + Reddit
      │
      ▼
Dedup (seen_urls.json)
      │
      ▼
LLM scores each item 1–10
against your interest profile
      │
      ▼
Render Markdown digest
+ intro paragraph
      │
      ▼
Print / save / email
```

## Extending

- **Add a source**: create a new file in `fetchers/`, return a list of `DigestItem`, call it in `main.py`
- **Add an output**: create a file in `outputs/`, call it in the output section of `main.py`
- **Email delivery**: set `delivery.email` in `config.yaml` (uses SMTP)

## License

MIT
