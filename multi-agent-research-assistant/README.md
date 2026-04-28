# 🔬 Multi-Agent Research Assistant

A lightweight multi-agent pipeline that takes any research topic and produces a comprehensive, cited markdown report in ~30 seconds.

**Planner** decomposes your topic → **Search agents** run in parallel → **Writer** synthesises a report.

No LangChain, no CrewAI — just clean async Python so you can see exactly how agents work.

## Demo

```
$ python main.py "The current state of fusion energy"

======================================================
  Research Agent
  Topic: The current state of fusion energy
======================================================

🧠 Planner: Decomposing 'The current state of fusion energy'...
  1. What are the latest breakthroughs in nuclear fusion research in 2024?
  2. Which companies and governments are leading fusion energy investment?
  3. What is the ITER project and what progress has it made?
  4. What are the main technical challenges preventing commercial fusion?
  5. When might fusion energy reach commercial viability?

📡 Running 5 search agents in parallel...
🔍 Search agent: 'What are the latest breakthroughs...'
🔍 Search agent: 'Which companies and governments...'
...

✍️  Writer: Synthesising 5 findings into report...
  ✓ Report complete

✅ Done in 28.4s
```

## Architecture

```
User topic
    │
    ▼
┌─────────────┐
│   Planner   │  LLM call → 3–5 sub-questions
└─────────────┘
    │
    ▼ (parallel)
┌──────┐ ┌──────┐ ┌──────┐
│ 🔍  │ │ 🔍  │ │ 🔍  │  Search + summarise each question
└──────┘ └──────┘ └──────┘
    │
    ▼
┌─────────────┐
│   Writer    │  LLM call → final markdown report + citations
└─────────────┘
```

## Quickstart

```bash
git clone https://github.com/yourname/research-agent
cd research-agent
pip install -r requirements.txt

cp .env.example .env
# Fill in GROQ_API_KEY (free at https://console.groq.com)
# Leave SERPER_API_KEY blank to use DuckDuckGo for free

python main.py "Your research topic here"
```

## Streamlit UI

```bash
streamlit run app.py
```

Opens a browser UI where you can enter topics and download reports.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `ollama`, or `openai` |
| `GROQ_API_KEY` | — | Free at console.groq.com |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Any Groq model |
| `OLLAMA_MODEL` | `llama3.2` | Any locally pulled model |
| `SERPER_API_KEY` | — | Optional. Falls back to DuckDuckGo |

### Running fully locally (no API keys)

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2

# Set in .env:
# LLM_PROVIDER=ollama
# Leave SERPER_API_KEY unset

python main.py "Your topic"
```

## Project structure

```
research_agent/
├── agents/
│   ├── llm.py        # LLM wrapper (Groq / Ollama / OpenAI)
│   ├── planner.py    # Breaks topic → sub-questions
│   ├── searcher.py   # Search + summarise one question
│   └── writer.py     # Synthesise all findings → report
├── tools/
│   └── search_tool.py  # Serper + DuckDuckGo wrappers
├── main.py           # CLI orchestrator
├── app.py            # Streamlit UI
├── requirements.txt
└── .env.example
```

## Extending

**Add a fact-checker agent** — after the writer, add an agent that verifies key claims against search results and flags uncertain statements.

**Add memory** — store past research runs in SQLite; let the planner consult previous findings before searching.

**Stream the report** — replace the writer's single `chat()` call with a streaming request and pipe tokens to the terminal / UI in real time.

**Add a CrewAI version** — the `agents/` folder maps cleanly to CrewAI's `Agent` + `Task` abstractions if you want to explore that framework.

## License

MIT
