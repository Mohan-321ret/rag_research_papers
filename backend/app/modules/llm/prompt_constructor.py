"""Prompt Constructor — the first stage of the generation pipeline.

    System Prompt + User Query + Retrieved Context -> LLM

Combines all three into a single flat string, since ``LLMProvider`` takes
one opaque ``prompt`` — this keeps every provider (Ollama's raw
completion endpoint, a chat API, a future local model) equally able to
consume it without needing a special system/user message split.
"""

DEFAULT_SYSTEM_PROMPT = (
    "You are an enterprise knowledge assistant. Answer the user's question "
    "using ONLY the numbered SOURCE blocks provided below. Cite every "
    "source you rely on with a [n] marker (e.g. [1], [2]) placed right "
    "after the statement it supports, where n matches that source's "
    "SOURCE number. If the sources do not contain the answer, say so "
    "plainly instead of guessing. Be concise and factual."
)


def build_prompt(query: str, context_text: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> str:
    """Assemble the final prompt handed to the LLM provider."""
    sections = [system_prompt.strip()]
    if context_text.strip():
        sections.append(context_text.strip())
    sections.append(f"Question: {query.strip()}")
    return "\n\n".join(sections)
