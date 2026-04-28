# LLM Wiki — Agent Instructions

You are the maintainer of this personal knowledge base. Read this file at the start of every session.

## Directory layout

```
llm-wiki/
├── AGENTS.md          ← you are here (schema + instructions)
├── sources/           ← raw inputs, IMMUTABLE — never edit these
│   └── *.md / *.txt / *.pdf (text extracted)
├── wiki/
│   ├── index.md       ← master catalog of all wiki pages
│   ├── log.md         ← append-only chronological record
│   ├── overview.md    ← high-level synthesis of the whole domain
│   └── **/*.md        ← concept, entity, and synthesis pages
└── scripts/
    ├── ingest.py      ← CLI: process a new source into the wiki
    ├── query.py       ← CLI: ask a question against the wiki
    └── lint.py        ← CLI: health-check the wiki
```

## Page conventions

Every wiki page (except index.md and log.md) starts with this frontmatter:

```
---
title: <title>
type: concept | entity | synthesis | source-summary | query-result
tags: [tag1, tag2]
sources: [filename1.md, filename2.md]
updated: YYYY-MM-DD
---
```

Then:
- A **one-sentence summary** immediately after the frontmatter (no heading).
- `## Overview` — main content
- `## Key points` — bullet list of the most important facts
- `## Connections` — links to related pages using `[[Page Title]]` syntax
- `## Open questions` — things worth investigating further
- `## Sources` — backlinks to raw source files that informed this page

## index.md format

index.md is a flat catalog. Update it on every ingest. Format:

```
## Concepts
- [[Page Title]] — one-line summary (N sources)

## Entities
- [[Name]] — one-line description

## Source summaries
- [[Article Title (YYYY-MM-DD)]] — one-line summary

## Query results
- [[Query: your question here]] — date
```

## log.md format

Append-only. Every entry starts with `## [YYYY-MM-DD] <type> | <title>` where type is one of: `ingest`, `query`, `lint`, `note`.

Example:
```
## [2026-04-23] ingest | "Attention Is All You Need"
Processed transformer paper. Created 3 new pages: [[Attention Mechanism]], [[Transformer Architecture]], [[Positional Encoding]]. Updated [[Neural Networks]].
```

## Operations

### On INGEST (when told to process a new source):
1. Read the source file carefully.
2. Briefly discuss key takeaways with the user (3-5 bullet points).
3. Create a `source-summary` page in `wiki/sources/`.
4. Create or update `concept` and `entity` pages for each major idea.
5. Flag any contradictions with existing wiki pages.
6. Update `wiki/index.md` with all new/changed pages.
7. Append an entry to `wiki/log.md`.
8. Optionally update `wiki/overview.md` if the source changes the big picture.

### On QUERY (when asked a question):
1. Read `wiki/index.md` to identify relevant pages.
2. Read those pages fully.
3. Synthesize an answer with `[[wiki page]]` citations.
4. Ask the user: "Should I save this as a wiki page?" If yes, write it as a `query-result` page and update the index.

### On LINT (when asked to health-check):
Scan the wiki and report:
- Pages with no inbound links (orphans)
- Contradictions between pages
- Concepts mentioned in text but without their own page
- Stale claims that newer sources have superseded
- Data gaps worth filling with a web search
- Suggested new questions to investigate

## Style rules
- Write in clear, neutral prose. No fluff.
- Prefer specific claims over vague generalizations.
- Every factual claim should have a source backlink.
- Use `[[Double brackets]]` for all internal wiki links.
- Keep pages focused — if a page exceeds ~500 words, consider splitting.
- Tag liberally. Tags help the LLM find related pages fast.
