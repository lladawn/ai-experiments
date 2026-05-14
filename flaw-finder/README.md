# Flaw Finder

Red-team your product before the market does.

Drop in a pitch deck, email, proposal, or website/app copy. Flaw Finder runs a
small panel of adversarial reviewers:

- **Skeptical investor**: market, differentiation, traction, and business model.
- **Hostile lawyer**: unsupported claims, privacy exposure, and liability.
- **Confused end-user**: clarity, next step, jargon, and time-to-value.

A synthesis pass ranks the highest-leverage fixes.

## Why this is experiment-friendly

- **Small local core**: no framework or API key required for the first loop.
- **Replaceable agents**: the reviewer rules can later become LLM prompts,
  evals, or hybrid rules without changing the product shape.
- **Traceable output**: every finding includes persona, severity, evidence, and
  a suggested fix.
- **Lab notebook included**: use `experiments/` to capture assumptions, methods,
  results, and decisions.

## Quickstart

```bash
cd /Users/dawn/Code/ai-experiments/flaw-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
flaw-finder examples/sample_pitch.md
```

Without installing, run it directly:

```bash
cd /Users/dawn/Code/ai-experiments/flaw-finder
PYTHONPATH=src python3 -m flaw_finder.cli examples/sample_pitch.md
```

Write a report:

```bash
PYTHONPATH=src python3 -m flaw_finder.cli examples/sample_pitch.md --output reports/sample-report.md
```

Run with a local Ollama model:

```bash
PYTHONPATH=src python3 -m flaw_finder.cli inputs/mumbl_wtf.md --ollama-model gemma4:latest --output reports/mumbl-wtf-gemma4.md
```

## Project structure

```text
flaw-finder/
├── examples/              # sample inputs
├── experiments/           # lab notebook
├── src/flaw_finder/
│   ├── agents.py          # persona reviewers and local rules
│   ├── cli.py             # command-line entrypoint
│   ├── models.py          # dataclasses for artifacts, findings, reviews
│   └── pipeline.py        # orchestration and markdown rendering
├── tests/
└── pyproject.toml
```

## Next build steps

1. Add LLM-backed reviewers behind the same `PersonaReviewer` shape.
2. Add extraction for PDFs, decks, and URLs.
3. Save reports to SQLite so runs can be compared.
4. Build a thin local web UI once the report format feels useful.
