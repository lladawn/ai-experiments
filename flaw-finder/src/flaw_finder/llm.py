from __future__ import annotations

import json
import urllib.request

from .models import InputArtifact


OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"


def run_ollama_red_team(artifact: InputArtifact, model: str) -> str:
    prompt = _build_prompt(artifact)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }
    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["response"].strip() + "\n"


def _build_prompt(artifact: InputArtifact) -> str:
    return f"""You are Flaw Finder, a product red-team system.

Review the artifact below as three different agents, then synthesize the fixes.
Be concrete, skeptical, and useful. Do not invent facts that are not in the artifact.

Agents:
1. Skeptical investor: punch holes in market, customer, distribution, retention, differentiation, and business model.
2. Hostile lawyer: punch holes in privacy, employment risk, anonymity claims, compliance, liability, and unsupported claims.
3. Confused end-user: punch holes in clarity, trust, onboarding, expectations, and whether they know what to do next.

Return markdown in this exact structure:

# Flaw Finder Report: {artifact.title}

## Executive Summary
One short paragraph with the overall diagnosis.

## Top Fixes
1. ...
2. ...
3. ...
4. ...
5. ...

## Skeptical Investor
- Severity: high|medium|low
- Issue:
- Evidence:
- Fix:

Repeat bullets for each material issue.

## Hostile Lawyer
- Severity: high|medium|low
- Issue:
- Evidence:
- Fix:

Repeat bullets for each material issue.

## Confused End-User
- Severity: high|medium|low
- Issue:
- Evidence:
- Fix:

Repeat bullets for each material issue.

## Assumptions
List any important assumptions or missing context.

Artifact source: {artifact.source}

Artifact:
\"\"\"
{artifact.body[:12000]}
\"\"\"
"""

