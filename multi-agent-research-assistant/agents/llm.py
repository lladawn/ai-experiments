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
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider}. Choose groq, ollama, or openai."
        )


async def _groq_chat(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com"
        )

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
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
    """
    Call the local Ollama chat API with sensible defaults and retries.

    Behavior improvements:
    - Respect OLLAMA_TIMEOUT env var (seconds) to override the per-request timeout.
    - Respect OLLAMA_MAX_RETRIES env var to override retry count (default 3).
    - Exponential backoff between retries.
    - Clearer errors on timeout or connection failures with actionable hints.
    """
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Resolve timeout (env var -> default)
    timeout_seconds = 120
    env_timeout = os.getenv("OLLAMA_TIMEOUT")
    if env_timeout:
        try:
            timeout_seconds = int(env_timeout)
            if timeout_seconds <= 0:
                timeout_seconds = 120
        except Exception:
            # ignore invalid env value and keep default
            timeout_seconds = 120

    # Resolve retry count (env var -> default)
    max_retries = 3
    env_retries = os.getenv("OLLAMA_MAX_RETRIES")
    if env_retries:
        try:
            r = int(env_retries)
            if r > 0:
                max_retries = r
        except Exception:
            pass

    import asyncio

    attempt = 0
    last_exc = None
    while attempt < max_retries:
        attempt += 1
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
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
                # Successful response
                return resp.json()["message"]["content"]
        except httpx.ReadTimeout as e:
            # Server accepted connection but did not respond in time
            last_exc = e
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                # Small informative print; avoid noisy logs for final failure
                try:
                    print(
                        f"[ollama] request timed out (attempt {attempt}/{max_retries}), retrying in {backoff}s..."
                    )
                except Exception:
                    pass
                await asyncio.sleep(backoff)
                continue
            # Final attempt failed: raise a clear, actionable error
            raise EnvironmentError(
                f"Ollama request timed out after {timeout_seconds} seconds. "
                "This often means the model is still loading or generating slowly. "
                "Options:\n"
                " - Increase timeout by setting the OLLAMA_TIMEOUT environment variable (seconds), e.g.\n"
                "     export OLLAMA_TIMEOUT=300\n"
                " - Increase retry attempts via OLLAMA_MAX_RETRIES, or call again later.\n"
                " - Ensure the model is pulled (e.g. `ollama pull <model>`) and that `ollama serve` is running.\n"
                " - Check your machine's resources (RAM/CPU/GPU) so the model can generate responses."
            ) from e
        except httpx.RequestError as e:
            # Covers connection errors and other network-related exceptions
            # Immediate failure — no retry if connection refused
            raise EnvironmentError(
                f"Failed to connect to Ollama at {base_url}. Is `ollama serve` running and accessible? "
                "If the server is running, check logs for errors or try restarting `ollama serve`."
            ) from e

    # If we exit loop unexpectedly, re-raise the last exception (defensive)
    if last_exc:
        raise last_exc
    raise EnvironmentError("Ollama request failed for unknown reasons.")


async def _openai_chat(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
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
