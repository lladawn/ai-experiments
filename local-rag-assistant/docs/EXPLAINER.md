# Notion Knowledge Assistant — Complete Explainer

> A deep-dive into the code architecture, technical concepts, and learning path behind this project.

---

## Table of Contents

1. [What This Project Does (Plain English)](#1-what-this-project-does-plain-english)
2. [Code Architecture](#2-code-architecture)
3. [Technical Architecture](#3-technical-architecture)
4. [The Pipeline — Step by Step](#4-the-pipeline--step-by-step)
5. [Core Concepts — What, Why, and How](#5-core-concepts--what-why-and-how)
6. [The Data Flow (End to End)](#6-the-data-flow-end-to-end)
7. [Things to Learn](#7-things-to-learn)

---

## 1. What This Project Does (Plain English)

You have years of notes in Notion — project logs, learnings, journal entries, meeting notes. The problem: you can't search them meaningfully. `Ctrl+F` finds exact words but misses context. You can't ask "what was I working on in Q3?" and get a useful answer.

This project solves that by:

1. **Reading all your Notion export files** (markdown, CSV, HTML)
2. **Understanding the meaning** of each chunk of text, not just the words
3. **Letting you ask questions in plain English** and finding the most relevant notes
4. **Extracting structured events** (date, project, action, insight) from your free-text notes
5. **Building a timeline** so you can see month-by-month what you worked on

Everything runs on your own machine. No data leaves your laptop. No API costs.

---

## 2. Code Architecture

### Folder Structure and Responsibility

```
notion-assistant/
│
├── src/                        # All application code
│   ├── config.py               # Central configuration loader
│   │
│   ├── ingest/                 # STAGE 1: Getting data in
│   │   ├── loader.py           # Read files from disk
│   │   ├── splitter.py         # Break text into chunks
│   │   └── embedder.py         # Convert chunks to numbers (vectors)
│   │
│   ├── extract/                # STAGE 2: Structuring data
│   │   ├── schema.py           # What a structured "event" looks like
│   │   └── extractor.py        # Ask LLM to pull events from text
│   │
│   ├── store/                  # STAGE 3: Storing data
│   │   ├── vector_store.py     # Store vectors in ChromaDB
│   │   └── event_store.py      # Store structured events in SQLite
│   │
│   ├── query/                  # STAGE 4: Using the data
│   │   ├── retriever.py        # Find relevant chunks for a question
│   │   ├── generator.py        # Generate an answer using found chunks
│   │   └── analytics.py        # Summarise activity over time
│   │
│   └── ui/
│       └── app.py              # Streamlit chat + timeline interface
│
├── scripts/
│   ├── run_ingest.py           # CLI to run the full pipeline
│   └── run_analytics.py        # CLI for analytics only
│
├── tests/
│   └── test_splitter.py        # Unit tests (no LLM needed)
│
├── data/                       # YOUR NOTION EXPORT (git-ignored)
├── db/                         # GENERATED DATABASES (git-ignored)
└── config.yaml                 # YOUR LOCAL CONFIG (git-ignored)
```

### Design Principles Used

**Single Responsibility** — every file does exactly one thing. `loader.py` only reads files. `splitter.py` only splits text. `embedder.py` only calls the embedding model. This makes each piece easy to understand, test, and replace independently.

**Separation of concerns** — the four stages (ingest, extract, store, query) are completely independent. You can re-run extraction without re-embedding. You can swap ChromaDB for a different vector store without touching the retriever.

**Idempotency** — running the ingest pipeline twice doesn't duplicate data. The loader tracks which files it has already processed using a SHA-256 hash of the file path and modification time. ChromaDB uses `upsert` (update or insert) rather than plain insert. This means you can safely re-run the pipeline whenever you add new notes.

**Fail gracefully** — the extractor validates every row the LLM returns using Pydantic. If the LLM returns garbage JSON, or a row is missing a required field, that row is silently dropped. The rest of the pipeline continues. This is important because local LLMs are imperfect — you don't want one bad page to crash a 40-minute extraction run.

---

## 3. Technical Architecture

### The Two Parallel Pipelines

This project actually runs two separate pipelines on your data, which feed two different use cases:

```
Your Notion Files
       │
       ▼
   [ Loader ]
       │
       ├──────────────────────────────────────────────┐
       │                                              │
       ▼                                              ▼
  [ Splitter ]                                 [ Extractor ]
  [ Embedder ]                                 (LLM reads page,
       │                                        returns JSON rows)
       ▼                                              │
  [ ChromaDB ]                                        ▼
  Vector Store                                  [ SQLite DB ]
  (semantic search)                             (structured events)
       │                                              │
       ▼                                              ▼
  [ Chat UI ]                                  [ Timeline UI ]
  "What did I learn                            "Show me what I
   about topic X?"                              worked on in 2024"
```

**Pipeline 1 (left side)** — Semantic search pipeline. Turns your notes into mathematical vectors and stores them. Used for chat — finding the most relevant passages for any question.

**Pipeline 2 (right side)** — Structured extraction pipeline. Uses the LLM to read each page and pull out structured rows: date, project, action, insight. Stored in SQLite. Used for the timeline and analytics.

### Storage Layer

| Store | Technology | What it holds | Why this tool |
|---|---|---|---|
| Vector store | ChromaDB | Chunks + embeddings | Purpose-built for vector similarity search, persistent, no server needed |
| Events store | SQLite | Structured event rows | Built into Python, zero setup, perfect for structured tabular data |
| Analytics | DuckDB | Reads from SQLite | Extremely fast analytical SQL queries on local files, great pandas integration |

### Models

| Model | Role | Size | Speed on M3 Pro |
|---|---|---|---|
| `mxbai-embed-large` | Convert text → vectors | 670MB | ~40ms per batch |
| `mistral-small3.2` | Chat + event extraction | ~14GB | ~15-20 tokens/sec |

Both run locally via **Ollama**, which acts as a local model server — the same way a web server serves web pages, Ollama serves model inference over a local HTTP API.

---

## 4. The Pipeline — Step by Step

### Step 1: Loading (`src/ingest/loader.py`)

Walks your `data/raw/` folder recursively and reads every supported file.

- `.md` files — parsed with `python-frontmatter` to separate YAML metadata (title, date, tags) from body content
- `.html` files — parsed with `BeautifulSoup`, stripping out script/style/nav noise to get clean text
- `.csv` files — Notion database exports, converted into readable prose rows ("Record: Name=X | Status=Y | Date=Z")

Each file becomes a `RawDocument` object with fields: `doc_id`, `source_path`, `title`, `content`, `metadata`.

The `doc_id` is a SHA-256 hash of the file path + modification time. If the file hasn't changed since last run, the same ID is produced, the loader recognises it's already been processed, and skips it.

### Step 2: Splitting (`src/ingest/splitter.py`)

A single page of notes might be 3,000 words. You can't embed the whole thing as one unit — the embedding would average out all the meaning and become vague. You need smaller, focused chunks.

The splitter breaks each document into overlapping chunks of ~600 characters with ~80 character overlap.

**Why overlap?** If a sentence is split across two chunks, you'd lose context at the boundary. Overlap ensures no idea is accidentally cut in half.

**Separator priority** — the splitter tries to break at `##` headings first, then paragraph breaks (`\n\n`), then single newlines, then sentences, then spaces. This means chunks tend to align with natural sections of your notes rather than cutting mid-sentence.

Each chunk carries the full provenance of its source: `doc_id`, `source_path`, `title`, `chunk_index`. This is what powers citations in the chat UI.

### Step 3: Embedding (`src/ingest/embedder.py`)

This is the conceptual heart of the system. Each chunk of text is converted into a list of 1024 numbers — a vector — by `mxbai-embed-large`. This vector represents the *meaning* of that chunk in mathematical space.

Chunks with similar meaning end up with vectors that are close together in that space. "Deployed the new API" and "shipped the backend service" would be very close. "Deployed the new API" and "went for a run" would be very far apart.

This is what makes semantic search possible — you can find relevant chunks even if they use completely different words than your question.

Chunks are embedded in batches of 32 and stored in ChromaDB along with their text and metadata.

### Step 4: Extraction (`src/extract/extractor.py`)

This is the structured data pipeline. For each page, the LLM is given a strict prompt:

> "Read this note. Return a JSON array of events. Each event must have: date, project, topic, action, insight, source_page. Respond with JSON only — no explanation."

The temperature is set to 0.1 (nearly deterministic) to make the output consistent and parseable.

The raw LLM response is then:
1. Stripped of any markdown code fences the model might add
2. Parsed as JSON
3. Each row validated against the `Event` Pydantic schema
4. Invalid rows silently dropped
5. Valid rows inserted into SQLite

### Step 5: Retrieval (`src/query/retriever.py`)

When you ask a question in the chat UI, the retriever finds the most relevant chunks.

It uses **hybrid search** — combining two scoring methods:

**Vector search (70% weight)** — your question is embedded into the same vector space as your chunks. ChromaDB finds the chunks with the closest vectors. Great for conceptual questions ("what did I learn about authentication?").

**BM25 keyword search (30% weight)** — a classical information retrieval algorithm that scores chunks by exact word frequency and rarity. Great for specific terms ("what happened with project Apollo?"). Built with `rank_bm25` over all stored chunk texts.

The two scores are combined with weighted addition and the top-k results are returned.

### Step 6: Generation (`src/query/generator.py`)

The retrieved chunks are assembled into a prompt:

```
Context from your notes:
[1] Source: Project Log (projects/apollo.md)
    ...chunk text...

[2] Source: Weekly Review (reviews/2024-03.md)
    ...chunk text...

Question: What was the status of project Apollo in March?
```

This prompt is sent to `mistral-small3.2`. The model is instructed to answer using only the provided context and cite its sources. The answer streams back token by token to the UI.

---

## 5. Core Concepts — What, Why, and How

### RAG — Retrieval Augmented Generation

**What:** A technique for making LLMs answer questions about your specific data, rather than just their training data.

**Why:** LLMs like Mistral were trained on internet text. They know nothing about your personal Notion notes. RAG solves this by finding the relevant pieces of your data first, then giving them to the LLM as context with the question.

**How it works here:**
```
User question
    → Embed question → vector
    → Search ChromaDB for similar chunk vectors
    → Retrieve top 6 chunks
    → Build prompt: "Given these chunks from the user's notes, answer: [question]"
    → LLM generates answer grounded in those chunks
```

Without RAG, you'd have to paste all 1,914 chunks into every prompt — which would be impossibly slow and expensive. RAG lets you find just the 6 most relevant chunks out of 1,914.

### Vector Embeddings

**What:** A way of representing the meaning of text as a list of numbers (a vector) in a high-dimensional space.

**Why:** Computers can't understand words directly, but they can do math on numbers. By converting text to vectors, you can calculate how similar two pieces of text are in meaning — even if they use completely different words.

**How it works here:** `mxbai-embed-large` converts each chunk into a 1024-dimensional vector. When you ask a question, it's converted to the same kind of vector. ChromaDB then finds the stored vectors that are closest to your question's vector using cosine similarity — a measure of the angle between two vectors in that 1024-dimensional space.

**Intuition:** Think of it like placing every chunk on a map where similar ideas are geographically close. Your question is also placed on that map, and you find the nearest neighbours.

### Cosine Similarity

**What:** A mathematical measure of how similar two vectors are, regardless of their magnitude.

**Why:** When comparing meaning, we care about direction (what the text is about), not magnitude (how long the text is). Cosine similarity measures the angle between two vectors — 1.0 means identical direction (identical meaning), 0.0 means perpendicular (no relationship).

**How it works here:** ChromaDB stores the index with `hnsw:space = cosine`. When you search, it returns distance scores (0 = identical, 2 = opposite). The code converts these to similarity scores with `1 - distance`.

### BM25

**What:** Best Match 25 — a classical keyword-based ranking algorithm from 1994, still widely used in search engines.

**Why:** Vector search is excellent for conceptual similarity but can miss exact proper nouns, project codenames, and specific dates. BM25 handles these well. Combining both gives you the best of both worlds.

**How it works:** BM25 scores a document for a query based on: how often the query words appear in the document (term frequency), how rare those words are across all documents (inverse document frequency), and the document length. Common words like "the" get very low scores; rare specific words like a project codename get high scores.

### Pydantic for LLM Output Validation

**What:** Pydantic is a Python library for data validation using type annotations.

**Why:** LLMs are probabilistic — they sometimes return slightly malformed JSON, use "null" as a string instead of `null`, invent plausible-sounding dates like "March 2024" instead of "2024-03", or omit required fields. Without validation, one bad response crashes the whole pipeline.

**How it works here:** Every JSON row the LLM returns is passed to `Event(**row)`. Pydantic checks: is `action` a non-empty string? Is `date` in YYYY-MM-DD format? Are optional fields actually null if the LLM wrote "n/a"? If validation fails, the row is caught in a `try/except` and silently dropped. The rest of the pipeline continues.

### SQLite + DuckDB — Two Tools for One Database

**Why two?**

SQLite is optimised for writes — inserting rows one at a time, updating records, managing transactions. It's the world's most deployed database and is built into Python.

DuckDB is optimised for reads — specifically for analytical queries that scan many rows and aggregate them. "Count events per month grouped by project" is exactly the kind of query DuckDB is built for. It can also directly attach and query a SQLite file, so there's no data duplication.

**The rule used here:** Write with SQLite, analyse with DuckDB.

### Ollama as a Local Model Server

**What:** Ollama is a tool that downloads, manages, and serves LLMs locally via an HTTP API.

**Why:** Running a 14GB model from scratch requires complex setup — downloading model weights, loading them into memory, managing GPU/CPU allocation. Ollama handles all of this. Your Python code just calls `ollama.chat(model="mistral-small3.2", messages=[...])` — identical in shape to calling the OpenAI API, but entirely local.

**How it works:** Ollama runs as a background process (`ollama serve`). When you call `ollama.chat()`, the Python SDK sends an HTTP POST to `localhost:11434`. Ollama loads the model into your 36GB unified memory, runs inference on the Apple Neural Engine + GPU cores, and streams tokens back.

### Idempotency via Content Hashing

**What:** Idempotent means running the same operation multiple times produces the same result — no duplicates, no errors.

**Why:** You'll re-run the ingest pipeline often — when you add new notes, when you want to re-extract events, or after a crash. Without idempotency, you'd get duplicate chunks in ChromaDB and duplicate events in SQLite.

**How it works here:** Each file gets a `doc_id` = SHA-256 hash of `(relative_path + modification_time)`. These IDs are stored in `data/processed/index.json`. On the next run, the loader skips any file whose ID is already in the index. ChromaDB's `upsert` uses the `chunk_id` as a primary key — inserting a chunk that already exists updates it rather than duplicating it.

---

## 6. The Data Flow (End to End)

Here is a complete trace of what happens when you ask: **"What did I work on for project Apollo?"**

```
1. You type the question in the Streamlit chat UI

2. app.py calls retriever.retrieve("What did I work on for project Apollo?")

3. retriever.py calls embed_query("What did I work on for project Apollo?")
   → ollama sends text to mxbai-embed-large
   → returns a 1024-dimensional vector, e.g. [0.023, -0.441, 0.187, ...]

4. retriever.py calls vector_store.search(query_vector, top_k=12)
   → ChromaDB computes cosine similarity between query vector
     and all 1,914 stored chunk vectors
   → returns top 12 closest chunks with their text and metadata

5. retriever.py builds a BM25 index from all stored texts
   → scores each of the 12 chunks for keyword overlap with the query
   → "Apollo" scores very high because it's a rare specific word

6. retriever.py combines:
   final_score = 0.7 × vector_score + 0.3 × bm25_score
   → re-ranks and returns top 6 chunks

7. app.py calls generate_answer_stream(question, hits)

8. generator.py builds this prompt:
   "Context from your notes:
    [1] Source: Apollo Project Log (projects/apollo.md)
        Week 3: Finished the authentication module. Blocked on DB schema.
    [2] Source: Weekly Review (reviews/2024-06-10.md)
        Spent most of the week on Apollo — finally got the pipeline working.
    ...
    Question: What did I work on for project Apollo?"

9. generator.py streams this to mistral-small3.2 via ollama.chat(stream=True)

10. Tokens stream back: "Based on your notes, you worked on project Apollo
    across several weeks in June 2024. You completed the authentication
    module [Page: projects/apollo.md] and later got the data pipeline
    working [Page: reviews/2024-06-10.md]..."

11. app.py renders each token as it arrives (streaming effect)

12. After the answer, app.py shows the Sources expander with links
    to the specific pages that were cited
```

---

## 7. Things to Learn

These are the concepts and technologies used in this project, ordered from foundational to advanced. Each one is a genuine skill worth building.

### Foundational — Start Here

**Python fundamentals**
The whole project is Python. Key patterns used: dataclasses, type hints, generators (`yield`), context managers (`with`), list comprehensions, `pathlib` for file handling. If any of these feel unfamiliar, they're worth learning properly before going deeper.

**How LLMs work (conceptual)**
You don't need to train one. But understanding tokens, context windows, temperature, and why models are probabilistic will help you write better prompts and debug unexpected outputs. Andrej Karpathy's "Intro to LLMs" video on YouTube is the best starting point.

**Markdown and file formats**
Your notes are in `.md` (Markdown) format with optional YAML front-matter. Understanding this format helps you understand what the loader is actually parsing and why `python-frontmatter` is needed.

### Core Skills — The Heart of This Project

**Vector embeddings and semantic search**
This is the most important concept in the project. Read about: what a vector space is, what cosine similarity measures, why sentence embeddings capture meaning, and what HNSW (the index algorithm ChromaDB uses) does. The Pinecone "What are Vector Embeddings?" guide is excellent.

**RAG (Retrieval Augmented Generation)**
The overall pattern this project implements. Once you understand embeddings, RAG is straightforward: embed your documents, embed the query, find nearest neighbours, stuff them into a prompt. LangChain's documentation has good conceptual explanations even if you're not using LangChain itself.

**Prompt engineering**
The extraction quality in this project is almost entirely determined by the prompt in `extractor.py`. Small changes to wording, ordering, or constraints produce dramatically different results. Learn about: system prompts vs user prompts, few-shot examples, chain-of-thought, JSON mode prompting.

**Pydantic**
The validation library used throughout. Learn the basics: `BaseModel`, `field_validator`, how validation errors work. Pydantic v2 is significantly different from v1 — make sure you're reading v2 docs.

### Infrastructure and Tools

**SQLite**
The built-in Python database. Learn basic SQL: `CREATE TABLE`, `INSERT`, `SELECT`, `GROUP BY`, `ORDER BY`, `COUNT`. SQLite Browser (a free GUI tool) is very useful for inspecting your `events.db` file visually.

**DuckDB**
A newer analytical database that's excellent for data exploration. Learn how it differs from SQLite (column-oriented vs row-oriented storage), how to use it from Python, and how `ATTACH` works for querying external files. The DuckDB docs are unusually good.

**Ollama**
Learn how to: list available models (`ollama list`), pull new models (`ollama pull`), check what's running (`ollama ps`), and understand the model naming convention (name:tag where tag is usually a quantisation level like `q4_k_m`).

**Streamlit**
The UI framework. Learn: `st.chat_message`, `st.session_state` (how to persist data across reruns), `st.cache_resource` (how to avoid reloading the database on every interaction), and `st.expander`. The Streamlit docs are beginner-friendly.

### Intermediate — Going Deeper

**Chunking strategies**
This project uses fixed-size character chunking. More advanced approaches include: semantic chunking (split at meaning boundaries, not character counts), recursive chunking, parent-child chunking (store small chunks for retrieval but large chunks for context). Each has trade-offs worth understanding.

**Hybrid search and re-ranking**
This project uses a simple weighted combination of BM25 and vector scores. Production systems use more sophisticated re-ranking: cross-encoders (a second model that re-scores retrieved pairs), reciprocal rank fusion, and learned sparse retrieval (SPLADE). Worth reading about once the basics are solid.

**Quantisation**
When you pull `mistral-small3.2`, Ollama defaults to a Q4_K_M quantised version. Quantisation reduces model precision (from 16-bit floats to 4-bit integers) to shrink the model from ~48GB to ~14GB with relatively small quality loss. Understanding Q4, Q5, Q8 trade-offs helps you choose the right model for your hardware.

**HNSW (Hierarchical Navigable Small World)**
The algorithm ChromaDB uses to find nearest neighbours efficiently. Without it, finding the closest vector out of 1,914 would require comparing your query to all 1,914 vectors (fine for this size, but slow at millions). HNSW builds a graph structure that lets you find approximate nearest neighbours in logarithmic time.

### Advanced — If You Want to Go Further

**Fine-tuning**
Instead of prompting a general model to extract events from your notes, you could fine-tune a smaller model specifically on your note style. The extraction would be faster and more accurate. Tools: `llama.cpp`, `MLX` (Apple Silicon optimised), `unsloth`.

**Evaluation**
How do you know if your RAG system is actually returning good answers? Learn about: RAGAS (a framework for evaluating RAG quality), precision/recall for retrieval, and how to build a small test set of question-answer pairs from your own notes to measure quality.

**Agent patterns**
Instead of a single retrieve-then-generate step, an agent can take multiple steps: search → read a result → decide to search again with a refined query → synthesise across multiple searches. `LangGraph` and `CrewAI` are popular frameworks. This would significantly improve answers to complex multi-hop questions ("What projects was I working on when I first started learning about X?").

---

*Built with: Python 3.12 · Ollama · ChromaDB · SQLite · DuckDB · Streamlit · LangChain Text Splitters · Pydantic v2 · rank-bm25 · mxbai-embed-large · mistral-small3.2*
