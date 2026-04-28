import json
import os
import httpx
from .models import DigestItem


async def score_and_summarize(
    items: list[DigestItem],
    interests: list[str],
    provider: str = "ollama",
    model: str = "llama3",
    max_items: int = 15,
) -> list[DigestItem]:
    """
    For each item (up to max_items), ask the LLM to:
      - Score relevance 1-10 against the user's interests
      - Write a one-line summary
    Returns items sorted by relevance score descending.
    """
    interest_str = ", ".join(interests)

    # Process in batches of 5 to keep prompts manageable
    batch_size = 5
    scored = []

    for i in range(0, min(len(items), max_items), batch_size):
        batch = items[i : i + batch_size]
        try:
            results = await _score_batch(batch, interest_str, provider, model)
            scored.extend(results)
        except Exception as e:
            print(f"  [llm] Scoring batch {i//batch_size + 1} failed: {e}")
            # fall back: keep items with score 5
            for item in batch:
                item.relevance_score = 5.0
                item.ai_summary = item.summary[:120]
                scored.append(item)

    scored.sort(key=lambda x: x.relevance_score, reverse=True)
    return scored


async def generate_digest_intro(
    top_items: list[DigestItem],
    interests: list[str],
    provider: str = "ollama",
    model: str = "llama3",
) -> str:
    """Generate a 2-3 sentence intro paragraph for the whole digest."""
    titles = "\n".join(f"- {item.title}" for item in top_items[:8])
    prompt = (
        f"You are writing the intro for a personal daily digest. "
        f"The reader is interested in: {', '.join(interests)}.\n\n"
        f"Today's top stories are:\n{titles}\n\n"
        f"Write a 2-3 sentence intro that highlights the most interesting theme or pattern "
        f"across today's stories. Be concise and engaging. No fluff."
    )
    try:
        return await _call_llm(prompt, provider, model)
    except Exception as e:
        print(f"  [llm] Intro generation failed: {e}")
        return "Here's your daily digest."


async def _score_batch(
    items: list[DigestItem],
    interest_str: str,
    provider: str,
    model: str,
) -> list[DigestItem]:
    items_text = ""
    for idx, item in enumerate(items):
        items_text += f"\n[{idx}] Title: {item.title}\nSource: {item.source}\nSnippet: {item.summary[:200]}\n"

    prompt = f"""You are a relevance scoring assistant. The user is interested in: {interest_str}.

Score each item below for relevance (1-10) and write a 1-sentence summary.
Return ONLY valid JSON as an array, one object per item, in the same order.
Each object must have exactly these keys: "score" (number 1-10), "summary" (string, max 120 chars), "tags" (array of 1-3 short strings).

Items:
{items_text}

JSON array:"""

    raw = await _call_llm(prompt, provider, model)

    # parse — strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)
    for idx, item in enumerate(items):
        if idx < len(parsed):
            item.relevance_score = float(parsed[idx].get("score", 5))
            item.ai_summary = parsed[idx].get("summary", "")[:120]
            item.tags = parsed[idx].get("tags", [])
    return items


async def _call_llm(prompt: str, provider: str, model: str) -> str:
    if provider == "ollama":
        return await _ollama(prompt, model)
    elif provider == "groq":
        return await _groq(prompt, model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _ollama(prompt: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"]


async def _groq(prompt: str, model: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY env var not set")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
