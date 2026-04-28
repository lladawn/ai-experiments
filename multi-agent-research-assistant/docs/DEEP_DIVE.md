# Multi-Agent Research Assistant — Deep Dive

A complete walkthrough of the architecture, concepts, design decisions, and learning opportunities in this project. Read this alongside the code — it explains not just *what* the code does but *why* each decision was made.

---

## Table of Contents

1. [What This Project Actually Does](#1-what-this-project-actually-does)
2. [Code Architecture](#2-code-architecture)
3. [Technical Architecture](#3-technical-architecture)
4. [Core Concepts — Explained](#4-core-concepts--explained)
5. [Design Decisions & Trade-offs](#5-design-decisions--trade-offs)
6. [How Each File Works](#6-how-each-file-works)
7. [The Debate Mode — How It's Different](#7-the-debate-mode--how-its-different)
8. [Things to Learn From This Project](#8-things-to-learn-from-this-project)
9. [What Could Be Added Next](#9-what-could-be-added-next)
10. [Glossary](#10-glossary)

---

## 1. What This Project Actually Does

You give it a topic — say, *"the impact of AI on jobs"* — and within ~30 seconds it returns a fully written, cited research report in markdown.

Under the hood, it doesn't just ask one LLM to write about the topic. It runs a **pipeline of specialised agents**, each doing one focused job:

```
"AI and jobs"
     │
     ▼
 Planner      → "What jobs are being automated by AI?"
               "What new jobs is AI creating?"
               "What does the research say about net job impact?"
               "Which industries are most affected?"
     │
     ▼ (all at once, in parallel)
 Searcher 1   → web search → summarise
 Searcher 2   → web search → summarise
 Searcher 3   → web search → summarise
 Searcher 4   → web search → summarise
     │
     ▼
 Writer       → synthesise all findings → final report with citations
```

This is meaningfully better than asking one LLM to write a report because:
- The planner ensures **broad coverage** — no single angle dominates
- The searchers ground the report in **real, current web data** — not just the LLM's training memory
- The writer has **all the evidence in front of it** before writing a single sentence

---

## 2. Code Architecture

### Directory layout

```
research_agent/
│
├── main.py                  ← Entry point. Orchestrates the pipeline.
├── app.py                   ← Streamlit UI (optional visual interface)
├── requirements.txt
├── .env.example
│
├── agents/                  ← The "brains" — each file is one agent
│   ├── __init__.py          ← Public API of the agents package
│   ├── llm.py               ← LLM wrapper (Groq / Ollama / OpenAI)
│   ├── planner.py           ← Decomposes topic → sub-questions
│   ├── searcher.py          ← Searches + summarises (neutral & debate)
│   └── writer.py            ← Synthesises findings → final report
│
└── tools/                   ← Utilities agents can use
    ├── __init__.py
    └── search_tool.py       ← Web search (Serper API or DuckDuckGo)
```

### The separation of concerns

There is a deliberate boundary between `agents/` and `tools/`:

**Agents** = things that think. They make LLM calls, reason about content, produce structured outputs.

**Tools** = things that act. They hit external APIs, fetch data, do I/O. No LLM calls inside tools.

This mirrors how frameworks like LangChain and CrewAI think about agents — an agent *uses* tools, but a tool doesn't use agents. Keeping this boundary makes the code easy to test (you can mock the search tool without touching agent logic) and easy to extend (swap DuckDuckGo for Bing by only changing `search_tool.py`).

### Data flow

```
str (topic)
  → planner.plan()         → list[str]         (sub-questions)
  → searcher.*()           → list[SearchFindings | DebateFindings]
  → writer.write_*()       → str               (markdown report)
```

Every function takes simple types in and returns simple types out. No shared global state, no class instances being passed around. This is intentional — it makes each agent independently testable and easy to reason about.

---

## 3. Technical Architecture

### The pipeline pattern

This project implements a **sequential pipeline with an internal parallel stage**:

```
Stage 1 (sequential):  Planner
Stage 2 (parallel):    N × Searcher agents  ← asyncio.gather()
Stage 3 (sequential):  Writer
```

Stage 2 is the interesting one. Because each sub-question is independent — the answer to "What jobs does AI create?" doesn't depend on the answer to "What jobs does AI destroy?" — we can search all of them simultaneously. `asyncio.gather()` fires all the coroutines at once and waits for all of them to finish.

Without parallelism, 5 sub-questions × ~5 seconds per search = 25 seconds just for searching.
With `asyncio.gather()`, all 5 run at the same time = ~5 seconds total.

### Async I/O — why it matters here

Python's `asyncio` is an **event loop**. When one coroutine is waiting on a network response (e.g., a web search), the event loop switches to running another coroutine instead of sitting idle.

This is perfect for this project because almost all the work is **I/O-bound** (waiting for HTTP responses from the LLM API and search API) rather than **CPU-bound** (heavy computation). Async I/O gives you concurrency without threads, avoiding race conditions and the overhead of thread management.

```python
# This is what happens without async (sequential):
result1 = search(q1)   # wait 5s
result2 = search(q2)   # wait 5s
result3 = search(q3)   # wait 5s
# Total: 15s

# This is what asyncio.gather() does (concurrent):
result1, result2, result3 = await asyncio.gather(
    search(q1),   # ─┐
    search(q2),   #  ├─ all fired at once, event loop interleaves waiting
    search(q3),   # ─┘
)
# Total: ~5s (limited by the slowest one)
```

### The LLM as a reasoning engine

Each agent uses the LLM differently:

| Agent | What it asks the LLM to do | Output format |
|-------|---------------------------|---------------|
| Planner | Decompose a topic into sub-questions | JSON array |
| Searcher | Summarise raw search results into prose | Free text |
| Writer | Synthesise multiple summaries into a report | Markdown |

Notice the planner asks for **structured output** (JSON). This is a key technique — when you need the LLM's output to be machine-readable (so you can loop over sub-questions), you constrain the output format in the system prompt and parse it. The planner's system prompt says: *"Respond ONLY with a JSON array of strings. No explanation, no markdown fences."*

The parser in `planner.py` also handles the case where the LLM wraps its output in markdown fences anyway (` ```json `). Defensive parsing like this is essential in production agentic systems — LLMs don't always follow instructions perfectly.

### Provider abstraction in `llm.py`

The `chat()` function is a **strategy pattern** — the same interface, different implementations selected at runtime via an environment variable:

```
LLM_PROVIDER=groq   → _groq_chat()   → api.groq.com
LLM_PROVIDER=ollama → _ollama_chat() → localhost:11434
LLM_PROVIDER=openai → _openai_chat() → api.openai.com (or any compatible endpoint)
```

This means you can develop locally with Ollama (zero cost, private), then switch to Groq for faster demos, without changing a single line of agent code. The agents just call `chat()` and don't care what's behind it.

This is how real production AI systems are built — you abstract the provider so you can swap models, control costs, and run experiments without touching business logic.

---

## 4. Core Concepts — Explained

### Agents

In this codebase, an "agent" is simply a **Python async function that makes one or more LLM calls to accomplish a specific task**. That's it. There's no magic.

More formally, an agent is a system that:
1. Receives some input
2. Reasons about it (using an LLM)
3. Optionally uses tools (search, code execution, etc.)
4. Returns a result

The "agentic" quality comes from the fact that the agent decides *how* to accomplish its task, not just *what* to do. The planner agent doesn't just concatenate text — it reasons about what aspects of a topic are most important to cover.

### Multi-agent systems

A multi-agent system is a collection of agents that work together, each specialised for a subtask. The key insight is **specialisation through system prompts**.

The planner's system prompt makes it think like a research strategist. The searcher's system prompt makes it think like a careful summariser. The writer's system prompt makes it think like a journalist. Same underlying LLM — totally different behaviour because of the instructions it's given.

This is more reliable than asking one general-purpose LLM to "research and write a report" in a single prompt, because:
- Each agent has a **narrow, well-defined job** it can do well
- Errors stay contained — a bad search summary affects one section, not the whole pipeline
- You can improve each agent independently without touching the others

### System prompts as agent personality

Every agent in this project has a `SYSTEM_PROMPT` constant at the top of its file. This is the agent's **identity** — it defines what role the LLM plays, what rules it follows, and what format to use for output.

Compare the planner's system prompt to the debate searcher's PRO and CON prompts:

- **Planner**: *"You are a research planning assistant... decompose into 3–5 specific sub-questions..."*
- **PRO searcher**: *"You are a research assistant building the strongest possible SUPPORTING case..."*
- **CON searcher**: *"You are a research assistant building the strongest possible OPPOSING case..."*

The same model, briefed differently, behaves completely differently. This is **prompt engineering** — the craft of writing instructions that reliably produce the behaviour you want.

### Structured outputs

When you need an LLM's response to be parsed by code, you use structured output prompting. The planner asks for a JSON array because the orchestrator needs to iterate over the sub-questions:

```python
sub_questions = json.loads(text)  # ["Q1", "Q2", "Q3"]
for q in sub_questions:           # loop only works if it's a list
    await search_and_summarize(q)
```

If the planner returned free prose ("Here are some questions: first, ..., second, ..."), the orchestrator couldn't parse it. Structured output bridges the gap between human-readable LLM responses and machine-parseable data.

### Tool use

In agent frameworks, a "tool" is a function the agent can call to interact with the outside world. In this project, the search tool is what gives agents access to current information beyond their training data.

The pattern is always: LLM decides what to search → tool executes the search → LLM reasons over the results. The LLM never directly touches the web; it only sees the results the tool returns.

### Context window as working memory

LLMs have no persistent memory between calls. Everything they "know" during a call is what's in their **context window** — the text passed in the current request.

This project deliberately manages context. The writer is given all the search summaries in one big prompt — that's its "working memory" for the task. Once the writer call returns, that context is gone. This is why stateful systems (like adding memory/history to this project) need an external store like SQLite or a vector database.

---

## 5. Design Decisions & Trade-offs

### Why no LangChain or CrewAI?

Frameworks like LangChain and CrewAI are powerful but they add abstraction on top of abstraction. For a learning project, that hides the concepts you're trying to understand.

This project does the same things those frameworks do — agent specialisation, tool use, parallel execution — but with plain Python. Once you understand what's happening here, picking up CrewAI or LangGraph takes an afternoon. Going the other direction (learning CrewAI first, then trying to understand what it's actually doing) is much harder.

### Why `httpx` instead of the `openai` SDK?

`httpx` is a raw HTTP client. Using it forces you to understand the actual API contract — what you send, what you get back. The Groq API is OpenAI-compatible, so the same `httpx` code works for both.

The `openai` SDK is more convenient in production, but it adds another layer of abstraction. For learning, raw `httpx` is better.

### Why `dataclasses` for `SearchFindings` and `DebateFindings`?

Dataclasses give you a typed, self-documenting structure for passing data between agents without the overhead of a full ORM or Pydantic model.

```python
@dataclass
class SearchFindings:
    question: str
    summary: str
    sources: list[SearchResult]
```

Anyone reading the code immediately knows exactly what a `SearchFindings` object contains. Compare to passing around raw dictionaries — `findings["summary"]` tells you nothing about what else the dict contains.

### Why DuckDuckGo as a fallback?

Zero friction for first-time setup. A new developer can clone, install, set one env var (GROQ_API_KEY), and run the project immediately — no Serper account, no credit card. The DuckDuckGo fallback removes a barrier to the first successful run, which is the most important moment for any demo project.

### Trade-off: breadth vs. depth

The current searcher only uses the **snippet** from search results — the 1-2 sentence preview — not the full page text. This is fast and cheap (no extra HTTP requests) but shallow. A production system would fetch and parse the full page for the top results. That's a natural next improvement (see section 9).

---

## 6. How Each File Works

### `tools/search_tool.py`

The simplest file. Defines one public function `search(query, num_results)` that returns `list[SearchResult]`.

Internally it checks for a `SERPER_API_KEY` environment variable. If present, it calls the Serper API (Google Search). If not, it falls back to `duckduckgo_search`, a third-party library that scrapes DuckDuckGo's HTML endpoint — no API key needed.

`SearchResult` is a dataclass with three fields: `title`, `url`, `snippet`. The `__str__` method formats it nicely for inclusion in LLM prompts.

### `agents/llm.py`

A single public function `chat(system, user, max_tokens)` that dispatches to the right provider based on `LLM_PROVIDER` env var.

All three providers (Groq, Ollama, OpenAI) use the same chat completions message format — a `system` message and a `user` message. This is the standard interface for instruction-following LLMs. The providers differ only in their endpoint URL, authentication header, and minor response JSON structure differences.

### `agents/planner.py`

Makes one LLM call. Passes the topic as the user message and a carefully written system prompt that instructs the model to respond with a JSON array.

The defensive JSON parsing (stripping ` ```json ` fences) is a practical necessity — even with explicit instructions, LLMs sometimes wrap their JSON in markdown code blocks. The parser handles both cases.

### `agents/searcher.py`

The most complex file. Contains three system prompts (neutral, pro, con) and three async functions:

`_summarize()` is a private helper — takes search results and a system prompt, formats the results as numbered text for the LLM, and returns a summary string.

`search_and_summarize()` is the original neutral mode: search once, summarise once.

`debate_search()` is the new mode: two searches in parallel (pro-framed and con-framed query), then two summarisations in parallel (using PRO_PROMPT and CON_PROMPT respectively), then returns a `DebateFindings` with both sides.

The key line in `debate_search()` is:
```python
pro_results, con_results = await asyncio.gather(
    search(pro_query, num_results=num_results),
    search(con_query, num_results=num_results),
)
```
This fires both searches simultaneously. Then immediately after:
```python
pro_summary, con_summary = await asyncio.gather(
    _summarize(question, pro_results, PRO_PROMPT),
    _summarize(question, con_results, CON_PROMPT),
)
```
Both LLM summarisation calls also run simultaneously. This means a single `debate_search()` call does 4 network requests (2 searches + 2 LLM calls) but takes roughly the time of 1.

### `agents/writer.py`

Two functions: `write_report()` for the neutral pipeline, `write_debate_report()` for debate mode.

Both work the same way: iterate over all findings, format them into a large structured text block, pass that block to the LLM with a system prompt that instructs it to write a formatted report. The writer prompt is the most elaborate in the project — it specifies the exact markdown structure, citation format, and tone.

The `ref_counter` variable incrementing across all findings ensures citations are globally unique — [1], [2], [3] across the whole report, not restarting at [1] for each section.

### `main.py`

The orchestrator. Imports from `agents/`, runs the pipeline, handles CLI arguments.

The `--debate` flag changes which branch of the pipeline runs:
```python
if debate:
    findings = await asyncio.gather(*[debate_search(q) for q in sub_questions])
    report = await write_debate_report(topic, list(findings))
else:
    findings = await asyncio.gather(*[search_and_summarize(q) for q in sub_questions])
    report = await write_report(topic, list(findings))
```

Everything else (planner, timing, output) is shared between modes.

---

## 7. The Debate Mode — How It's Different

The debate mode is architecturally the same pipeline — planner → searchers → writer — but with two key changes:

**1. Query framing in the searcher**

Instead of searching the raw sub-question, debate mode constructs two biased queries:
```python
pro_query = f"evidence supporting {question}"
con_query = f"criticism against {question}"
```

This is a simple but effective technique. Search engines surface different documents based on the framing of the query. "evidence supporting nuclear energy" and "criticism against nuclear energy" will return genuinely different articles, giving the two agents different raw material to work from.

**2. System prompt as adversarial framing**

The PRO and CON system prompts explicitly instruct the LLM to argue one side and ignore the other:

> *"Focus only on supporting evidence; ignore counterarguments."*

This is deliberate. An LLM asked to "summarise both sides" will produce mush — it hedges everything. By separating the two perspectives into different LLM calls with explicit instructions, you get stronger, more distinct arguments on each side.

**3. The writer's verdict**

The debate writer's system prompt includes this instruction:

> *"Be honest if one side has stronger evidence — don't force false balance."*

This is important. Many AI systems produce false balance — treating a consensus scientific position and a fringe view as equally credible because "there are two sides." The verdict section is meant to cut through that: if the evidence overwhelmingly supports one side, the report should say so.

---

## 8. Things to Learn From This Project

### Python concepts demonstrated here

**`async`/`await` and `asyncio`** — The backbone of the parallelism. Understanding the event loop, coroutines vs. threads, and when async is better than threading is essential for any modern Python I/O work.

**`asyncio.gather()`** — Runs multiple coroutines concurrently and collects their results. The most important single function in this codebase.

**`dataclasses`** — A clean way to define data-carrying objects without boilerplate. Used for `SearchResult`, `SearchFindings`, `DebateFindings`.

**`httpx.AsyncClient`** — Async HTTP client. The async equivalent of `requests`. Used for all API calls. Understanding `async with` context managers is part of this.

**Environment variables and `.env` files** — `python-dotenv` loads `.env` into `os.environ`. Standard practice for keeping API keys out of code.

**Package structure** — `__init__.py` files, relative imports (`.llm`, `.searcher`), how Python resolves module paths. The `agents/` and `tools/` folders are proper packages, not just folders.

### AI / LLM concepts demonstrated here

**System prompts** — How to write instructions that reliably shape LLM behaviour. Compare the three system prompts in `searcher.py` to see how the same model produces completely different output.

**Structured output prompting** — Asking the LLM for JSON and parsing it. The planner is a clean example.

**Prompt decomposition** — Breaking a complex task ("research this topic") into smaller prompts, each focused on one thing. The key skill in prompt engineering.

**Context management** — Deliberately constructing the input to each LLM call. The writer prompt is a lesson in how to give an LLM exactly what it needs and nothing more.

**Provider abstraction** — How to write LLM-provider-agnostic code. Real systems need this.

### Software design concepts

**Pipeline pattern** — A sequence of processing stages where each stage's output is the next stage's input. Common in data engineering, compilers, and AI systems.

**Strategy pattern** — `llm.py`'s provider dispatch is a textbook strategy pattern. Same interface, swappable implementations.

**Separation of concerns** — `agents/` vs `tools/` boundary. Agents think, tools act.

**Defensive programming** — The JSON fence stripping in `planner.py`. Always assume the external system (LLM, API) might not behave exactly as documented.

---

## 9. What Could Be Added Next

### Short extensions (hours)

**Streaming output** — Instead of waiting for the full writer response, stream tokens to the terminal as they arrive. Groq and Ollama both support `stream: true`. The UX improvement is dramatic.

**Auto-save reports** — After every run, automatically save the report to `reports/YYYY-MM-DD_topic.md`. Builds a personal research archive you can search later.

**Follow-up Q&A** — After the report is generated, drop into an interactive loop where the user can ask follow-up questions. A simple `while True: input()` loop that passes the report + question to a new LLM call.

**Token/cost logging** — Log how many tokens each LLM call uses. Groq's response includes token counts. Useful for understanding costs and optimising prompts.

### Meaningful improvements (half a day)

**Full-page scraping** — Instead of just using the search snippet, fetch the full HTML of the top 2 results per question and extract the main text. Much richer summaries. Use `httpx` + `BeautifulSoup`.

**Fact-checker agent** — A 4th agent that reads the final report, extracts the key factual claims, re-searches each one, and appends a confidence section. Catches LLM hallucinations introduced by the writer.

**Agent memory (SQLite)** — Store past research runs in a local SQLite database. Before searching, the planner checks if a similar question was recently answered and reuses the result. Demonstrates stateful agents.

**Source quality filter** — After fetching search results, a small LLM call rates each source's credibility (domain, title, snippet) and filters out low-quality ones before summarising. Improves report quality significantly.

### Bigger features (day project)

**Iterative deep research** — After the first report, a critic agent reads it, identifies gaps and unanswered questions, and triggers a second round of planning + searching to fill them. Run 2-3 iterations. This is what products like Perplexity Deep Research do.

**Telegram / Discord bot** — Wrap the pipeline in a bot. Message it a topic, get a report back. The pipeline is already async so it maps cleanly onto a bot handler.

**Vector memory** — Store all past reports and their source chunks in a vector database (Chroma, Qdrant — both free). Before searching the web, check if relevant information already exists in memory. Efficient and demonstrates RAG (Retrieval-Augmented Generation).

**Evaluation harness** — Write a test suite that runs the pipeline on known topics and checks: Did the report cover all the key points? Were citations included? Was the report structured correctly? Automated evals are how you safely improve prompts without regressions.

---

## 10. Glossary

**Agent** — A system that uses an LLM to reason about a task and optionally calls tools to accomplish it.

**asyncio** — Python's standard library for writing concurrent code using the async/await syntax and an event loop.

**Context window** — The maximum amount of text an LLM can process in a single call. Everything the model "knows" during a call is in its context window.

**Coroutine** — A Python function defined with `async def`. It can be paused (with `await`) to let other coroutines run, enabling concurrent execution without threads.

**Dataclass** — A Python class decorator (`@dataclass`) that auto-generates `__init__`, `__repr__`, and other methods from field annotations.

**Event loop** — The core of asyncio. A loop that runs coroutines, switching between them whenever one is waiting on I/O.

**Grounding** — Connecting LLM output to real-world data (e.g., search results, databases) to reduce hallucinations and add recency.

**Hallucination** — When an LLM confidently states something that isn't true. A known failure mode, especially for specific facts like statistics, dates, and quotes.

**Pipeline** — A data processing pattern where output from one stage becomes input to the next.

**Prompt engineering** — The practice of crafting LLM instructions (system prompts, user messages) to reliably produce desired behaviour.

**RAG (Retrieval-Augmented Generation)** — A pattern where relevant documents are retrieved (e.g., from a vector database or web search) and included in the LLM prompt, giving it grounded context to generate from.

**Strategy pattern** — A software design pattern where a family of algorithms is defined, each encapsulated, and made interchangeable. Used in `llm.py` for provider selection.

**Structured output** — Prompting an LLM to respond in a specific machine-readable format (JSON, XML) so the output can be parsed by code.

**System prompt** — Instructions given to an LLM before the user's message. Defines the model's role, behaviour rules, and output format. Invisible to the end user in most interfaces.

**Tool use** — The ability of an agent to call external functions (search, code execution, APIs) to gather information or take actions in the world.
