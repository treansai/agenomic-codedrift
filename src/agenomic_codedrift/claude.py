"""Thin wrapper around the Anthropic SDK with retry/backoff."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import anthropic
from anthropic import APIStatusError, APITimeoutError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024
PROMPT_TEMPLATE = (
    "Refactor the following Python function for clarity and add complete "
    "type hints. Return only valid Python code, no commentary, no markdown "
    "fences.\n\n```python\n{source}\n```"
)


@dataclass(frozen=True)
class ClaudeResponse:
    model: str
    text: str
    input_tokens: int
    output_tokens: int


def make_client(api_key: str | None = None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])


def refactor_snippet(
    client: anthropic.Anthropic,
    source: str,
    *,
    model: str = DEFAULT_MODEL,
    max_retries: int = 3,
) -> ClaudeResponse:
    """Ask Claude to refactor `source`. Exponential backoff on 429/timeout."""
    delays = [1, 4, 16]
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=DEFAULT_MAX_TOKENS,
                messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(source=source)}],
            )
            text_parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
            return ClaudeResponse(
                model=msg.model,
                text="".join(text_parts).strip(),
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
            )
        except (APIStatusError, APITimeoutError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break
            logger.warning(
                "claude call attempt %d failed (%s); retrying in %ds",
                attempt + 1,
                type(exc).__name__,
                delays[attempt],
            )
            time.sleep(delays[attempt])
    assert last_exc is not None
    raise last_exc
