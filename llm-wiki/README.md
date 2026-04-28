# LLM Wiki — Your Personal Compounding Knowledge Base

Based on [Andrej Karpathy's llm-wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

The idea: instead of uploading docs to an AI chatbot and getting one-shot answers, you build a **persistent wiki** that the LLM maintains. Every source you add enriches it. Every question you ask can be saved back into it. Knowledge compounds instead of evaporating.

---

## Setup (5 minutes)

### 1. Install dependencies
```bash
pip install anthropic
```

### 2. Set your API key
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Open the wiki in Obsidian (optional but great)
Download [Obsidian](https://obsidian.md/) and open the `wiki/` folder as a vault.
The graph view becomes your knowledge map.

---

## Directory structure

```
llm-wiki/
├── AGENTS.md          ← agent instructions (the "schema")
├── README.md          ← this file
├── sources/           ← raw inputs (IMMUTABLE — never edited by the LLM)
├── wiki/
│   ├── index.md       ← master catalog of all pages
│   ├── log.md         ← append-only activity log
│   ├── overview.md    ← high-level synthesis
│   ├── sources/       ← source summary pages (one per raw source)
│   └── queries/       ← saved query-result pages
└── scripts/
    ├── ingest.py      ← add a new source
    ├── query.py       ← ask a question
    └── lint.py        ← health-check the wiki
```

---

## The three operations

### 1. Ingest a source
Drop any markdown/text file into `sources/` and run:

```bash
python scripts/ingest.py sources/my-article.md
```

Claude will:
- Summarize the source
- Create/update concept and entity pages
- Update index.md and log.md
- Flag contradictions with existing knowledge

**Works with:** articles (paste as .md), paper summaries, meeting notes, book chapters, podcast transcripts, your own journal entries.

**To convert a web article:** Use the [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension or paste the text into a .md file.

**To convert a PDF:** Copy-paste the text, or use `pdftotext`:
```bash
pdftotext paper.pdf sources/paper.md
```

### 2. Query the wiki
```bash
python scripts/query.py "What are the main themes in my research?"
python scripts/query.py "Compare X and Y" --save
python scripts/query.py "Give me a slide deck on transformers" --format marp
```

Answers cite `[[wiki pages]]`. Use `--save` to write the answer back into the wiki as a new page (this is powerful — your queries compound too).

### 3. Lint (health check)
```bash
python scripts/lint.py           # fast local checks
python scripts/lint.py --fix     # LLM deep check: contradictions, gaps, suggestions
```

---

## Workflow tips

**Start narrow.** Pick one topic (your research area, a book you're reading, a project) rather than trying to index everything at once.

**Ingest one source at a time.** Stay in the loop. Read the summaries, check the updates. The wiki quality degrades when you batch-ingest without supervision.

**Let answers compound.** When you get a good synthesis from a query, save it back with `--save`. Your explorations become part of the knowledge base.

**Use the Obsidian graph.** Hub pages (lots of connections) show you what concepts dominate your domain. Isolated nodes show gaps.

**Run lint weekly.** The LLM will suggest new questions and sources you hadn't thought of.

---

## Scaling beyond ~200 pages

At small scale (<200 pages), the flat index.md approach works great — Claude reads the whole index and drills into relevant pages. When you get larger:

- Add semantic search: embed wiki pages with `sentence-transformers` and do vector lookup before reading full pages.
- Add a knowledge graph: use `networkx` to track relationships between concepts.
- Split the index: one index per domain/category.

For a week-1 build, don't worry about this yet.

---

## Cost estimate

Using `claude-sonnet-4-6`:
- Ingest a 2000-word article: ~$0.01–0.03
- Query: ~$0.005–0.01
- Lint: ~$0.02

A full week of active use (50 sources, 100 queries): ~$2–5.

---

## Inspiration

- [Karpathy's original tweet](https://x.com/karpathy/status/2039805659525644595)
- [Karpathy's llm-wiki.md gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Vannevar Bush's Memex (1945) — the original vision of a personal associative knowledge machine
