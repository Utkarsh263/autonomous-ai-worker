"""
The "thinking" part of the agent: turning a natural language task into a
target to act on, and later deciding what to do when a step fails.

Design note (this is the main thing worth explaining in an interview):
This is a hybrid reasoner, not a single hard-coded parser and not a full
LLM-agent framework either.

  - If ANTHROPIC_API_KEY is set in the environment, it asks Claude to pull
    the target company name out of the task sentence. This is the
    "generalizes to a differently-worded task" path.
  - If no key is set (e.g. for grading/demo without secrets), it falls
    back to a simple regex ("invoice from <Company>") that handles the
    same sentence shapes the brief itself uses as examples.

Both paths return the exact same shape, so the rest of the agent (worker.py)
doesn't know or care which one ran. That's the one piece of "pluggable
reasoning" this prototype aims for -- deliberately not more than that,
since the brief asks for a narrow prototype that really works over a
broad one that mostly doesn't.
"""

import os
import re


def parse_task(task_text):
    """
    Returns {"company": str | None, "raw_task": task_text}.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        company = _parse_with_llm(task_text, api_key)
        if company:
            return {"company": company, "raw_task": task_text, "used_llm": True}
        # fall through to regex if the LLM call fails or returns nothing usable

    company = _parse_with_regex(task_text)
    return {"company": company, "raw_task": task_text, "used_llm": False}


def _parse_with_regex(task_text):
    match = re.search(r"from\s+([A-Z][A-Za-z0-9&.'\- ]+?)(?:,| and| who| that| to|\.|$)", task_text)
    if match:
        return match.group(1).strip()
    return None


def _parse_with_llm(task_text, api_key):
    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": (
                    "Extract only the company name this task refers to. "
                    "Reply with the company name alone, nothing else.\n\n"
                    f"Task: {task_text}"
                ),
            }],
        )
        text = response.content[0].text.strip()
        return text if text else None
    except Exception:
        return None
