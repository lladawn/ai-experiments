from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import request


@dataclass(frozen=True)
class ModelResponse:
    answer: str
    tool_calls: tuple[tuple[str, dict[str, str]], ...] = ()


class Model(Protocol):
    def complete(self, prompt: str) -> ModelResponse:
        ...


class StubModel:
    def complete(self, prompt: str) -> ModelResponse:
        if "Allowed Tools" in prompt:
            return ModelResponse(
                answer="I will inspect the provided context and use the allowed tools only.",
                tool_calls=(("echo_context", {"note": "context received"}),),
            )
        return ModelResponse(answer="I can answer from the isolated context.")


class OllamaModel:
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def complete(self, prompt: str) -> ModelResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        data = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(http_request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))

        return ModelResponse(answer=body.get("response", "").strip())


class JsonToolOllamaModel(OllamaModel):
    def complete(self, prompt: str) -> ModelResponse:
        response = super().complete(
            prompt
            + "\n\nReturn JSON only with this shape: "
            + '{"answer": "text", "tool_calls": [{"name": "tool", "args": {"key": "value"}}]}. '
            + "Use an empty tool_calls array when no tool is needed."
        )
        parsed = _parse_json_object(response.answer)
        if parsed is None:
            return response

        tool_calls = []
        for call in parsed.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            args = call.get("args", {})
            if isinstance(name, str) and isinstance(args, dict):
                tool_calls.append((name, {str(key): str(value) for key, value in args.items()}))

        return ModelResponse(
            answer=str(parsed.get("answer", "")).strip(),
            tool_calls=tuple(tool_calls),
        )


def _parse_json_object(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        value = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
