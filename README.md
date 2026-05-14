# AI Experiments

A collection of small, practical AI projects exploring local-first assistants,
agent pipelines, retrieval, personal knowledge systems, and MCP servers. Each
project is self-contained and has its own README with setup and usage details.

## Projects

| Project | What it does | Main ideas |
| --- | --- | --- |
| [`daily-digest-agent`](daily-digest-agent/) | Builds a personalized daily Markdown digest from RSS, Hacker News, and Reddit. | Local or API-backed LLM scoring, summarization, deduplication, configurable sources. |
| [`mac-agent-app`](mac-agent-app/) | Native macOS shell for a local desktop agent runtime. | Menu bar app, overlay, double-E hotkey, command intake, native speech experiments. |
| [`llm-wiki`](llm-wiki/) | Maintains a persistent LLM-assisted wiki from source documents and saved queries. | Compounding knowledge base, source ingestion, Obsidian-friendly wiki pages, Anthropic or Ollama backend. |
| [`local-rag-assistant`](local-rag-assistant/) | Lets you chat with a local Notion export and extract structured timelines from it. | Local RAG, ChromaDB, SQLite, DuckDB analytics, Streamlit UI, Ollama models. |
| [`multi-agent-research-assistant`](multi-agent-research-assistant/) | Produces cited research reports from a topic using planner, searcher, and writer agents. | Async multi-agent workflow, web search, provider abstraction, CLI and Streamlit interfaces. |
| [`tiny-memory-mcp`](tiny-memory-mcp/) | Provides durable local memory to MCP-compatible AI clients. | Model Context Protocol, SQLite-backed memory, stdio and Streamable HTTP transports, Docker/ngrok deployment. |

## Project Summaries

### Daily Digest Agent

`daily-digest-agent` fetches new items from configured sources, filters out
previously seen links, scores each item against your interests, and renders a
clean Markdown digest. It can use Ollama for a fully local workflow or Groq for
a hosted free-tier option.

Start here:

```bash
cd daily-digest-agent
pip install -r requirements.txt
python main.py
```

### Mac Agent App

`mac-agent-app` is a native macOS shell for a local desktop agent runtime. It
provides a menu bar app, floating overlay, double-`E` hotkey, command panel,
speech experiments, and daemon launcher.

Start here:

```bash
cd mac-agent-app
scripts/build-dev-app.sh
open "dist/Mac Agent.app"
```

### LLM Wiki

`llm-wiki` is based on Andrej Karpathy's persistent wiki pattern. Instead of
getting one-off answers from a chatbot, you add sources to a durable markdown
wiki that the LLM updates over time. Ingested documents become summaries,
concept pages, index updates, and activity log entries; useful query answers can
also be saved back into the wiki.

Start here:

```bash
cd llm-wiki
pip install -r requirements.txt
python scripts/ingest.py sources/my-article.md
python scripts/query.py "What are the main themes?"
```

### Local RAG Assistant

`local-rag-assistant` is a private Notion knowledge assistant. It ingests a
Notion Markdown/CSV export, chunks and embeds the content locally with Ollama,
stores vectors in ChromaDB, extracts structured events into SQLite, and exposes
chat plus timeline workflows through Streamlit.

Start here:

```bash
cd local-rag-assistant
pip install -r requirements.txt
cp config.example.yaml config.yaml
python scripts/run_ingest.py
streamlit run src/ui/app.py
```

### Multi-Agent Research Assistant

`multi-agent-research-assistant` turns a research topic into a cited Markdown
report. A planner decomposes the topic into sub-questions, search agents run
those questions in parallel, and a writer synthesizes the findings. It supports
Groq, Ollama, and OpenAI-style providers, with DuckDuckGo search available when
Serper is not configured.

Start here:

```bash
cd multi-agent-research-assistant
pip install -r requirements.txt
python main.py "The current state of fusion energy"
```

### Tiny Memory MCP

`tiny-memory-mcp` is a dependency-free Python MCP server that gives an AI client
durable local memory. It stores memories in SQLite and exposes tools to remember,
recall, list, fetch, search, and forget records. It can run over stdio for local
MCP hosts or over Streamable HTTP for remote connector-style usage.

Start here:

```bash
cd tiny-memory-mcp
python3 server.py
python3 tests/smoke.py
```

## Common Themes

- **Local-first AI:** several projects can run with Ollama so private data stays
  on the machine.
- **Small, inspectable systems:** most projects avoid large agent frameworks so
  the core mechanics are visible in plain Python.
- **Persistent memory and knowledge:** projects explore durable stores such as
  Markdown, SQLite, ChromaDB, and DuckDB.
- **Agent workflows:** the repo includes examples of single-purpose agents,
  multi-agent pipelines, tool use, and MCP integration.

## Suggested Reading Order

1. Start with `daily-digest-agent` for a simple end-to-end local agent.
2. Read `multi-agent-research-assistant` to see planner/searcher/writer
   orchestration.
3. Explore `local-rag-assistant` for a fuller retrieval and analytics pipeline.
4. Try `llm-wiki` for a markdown-native personal knowledge workflow.
5. Finish with `tiny-memory-mcp` to understand how AI clients can use external
   memory through MCP.

## Notes

- Each project has its own dependencies and setup steps.
- Generated data, local databases, API keys, and private exports should stay out
  of git.
- Check each project's README before running it; several require local services
  such as Ollama, Streamlit, Docker, or API keys.
