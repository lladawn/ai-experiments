"""
LLM wrapper — supports Groq (fast free tier) and Ollama (fully local).

Set LLM_PROVIDER in .env:
  LLM_PROVIDER=groq     → uses Groq API (set GROQ_API_KEY)
  LLM_PROVIDER=ollama   → uses local Ollama (set OLLAMA_MODEL, default: llama3.2)
  LLM_PROVIDER=openai   → uses OpenAI-compatible endpoint (set OPENAI_API_KEY, OPENAI_BASE_URL)
"""

import os
import httpx


async def chat(system: str, user: str, max_tokens: int = 1000) -> str:
    """Send a chat message and return the assistant's reply."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        return await _groq_chat(system, user, max_tokens)
    elif provider == "ollama":
        return await _ollama_chat(system, user, max_tokens)
    elif provider == "openai":
        return await _openai_chat(system, user, max_tokens)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Choose groq, ollama, or openai.")


async def _groq_chat(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set. Get a free key at https://console.groq.com")

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _ollama_chat(system: str, user: str, max_tokens: int) -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {"num_predict": max_tokens},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


async def _openai_chat(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
