"""
Planner agent — given a research topic, returns 3–5 focused sub-questions
that together would produce a comprehensive report.
"""

import json
from .llm import chat


SYSTEM_PROMPT = """You are a research planning assistant.
Given a research topic, decompose it into 3–5 specific, focused sub-questions.
Each sub-question should:
- Be independently searchable (good as a web search query)
- Cover a different angle of the topic
- Together give a comprehensive picture

Respond ONLY with a JSON array of strings. No explanation, no markdown fences.
Example: ["What is X?", "How does X work?", "What are the limitations of X?"]"""


async def plan(topic: str) -> list[str]:
    """Break a topic into sub-questions."""
    print(f"\n🧠 Planner: Decomposing '{topic}'...")

    response = await chat(
        system=SYSTEM_PROMPT,
        user=f"Research topic: {topic}",
    )

    # Parse JSON array from response
    text = response.strip()
    # Strip markdown fences if the LLM adds them anyway
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    sub_questions = json.loads(text)
    assert isinstance(sub_questions, list), "Expected a JSON array"

    for i, q in enumerate(sub_questions, 1):
        print(f"  {i}. {q}")

    return sub_questions
