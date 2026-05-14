from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .llm import run_ollama_red_team
from .models import InputArtifact
from .pipeline import render_markdown, run_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Red-team a pitch, proposal, email, or landing-page draft.")
    parser.add_argument("input", nargs="?", help="Path to a text/markdown file. Reads stdin when omitted.")
    parser.add_argument("--title", default="Untitled artifact", help="Human-readable title for the report.")
    parser.add_argument("--output", help="Optional path for the markdown report.")
    parser.add_argument("--ollama-model", help="Run an LLM-backed red team with a local Ollama model.")
    args = parser.parse_args(argv)

    artifact = _load_artifact(args.input, args.title)
    if args.ollama_model:
        report = run_ollama_red_team(artifact, model=args.ollama_model)
    else:
        report = render_markdown(run_review(artifact))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    return 0


def _load_artifact(input_path: str | None, title: str) -> InputArtifact:
    if input_path:
        path = Path(input_path)
        return InputArtifact(title=title if title != "Untitled artifact" else path.stem, body=path.read_text(), source=str(path))
    return InputArtifact(title=title, body=sys.stdin.read(), source="stdin")


if __name__ == "__main__":
    raise SystemExit(main())
