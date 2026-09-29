"""Conversation loop: Claude + the calculation tools, with history kept across turns."""

from __future__ import annotations

import os
from collections.abc import Callable

import anthropic

from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS

MODEL = os.environ.get("KHABEER_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("KHABEER_EFFORT", "high")
MAX_TOKENS = 16000


class TurnFailed(Exception):
    """The turn could not complete; history has been rolled back."""


class Khabeer:
    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()
        self.messages: list[dict] = []

    def ask(self, text: str, on_tool: Callable[[str, dict], None] | None = None) -> str:
        """Send one user message, run any tool calls, return the final answer text."""
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": text})
        try:
            return self._run(on_tool)
        except BaseException:
            del self.messages[checkpoint:]
            raise

    def _run(self, on_tool: Callable[[str, dict], None] | None) -> str:
        runner = self.client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=list(self.messages),
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},
            # On a safety decline, the API retries on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        last = None
        for message in runner:
            last = message
            # The runner keeps its own copy of the history; mirror it (thinking
            # blocks included, unchanged) so the next turn continues the conversation.
            self.messages.append({"role": "assistant", "content": message.content})
            if message.stop_reason == "refusal":
                raise TurnFailed("رُفض الطلب لأسباب تتعلّق بسياسة الاستخدام.")
            if message.stop_reason == "max_tokens":
                raise TurnFailed("الجواب أطول من الحدّ المسموح؛ اطلب جزءاً أصغر أو قسّم المهمّة.")
            if on_tool:
                for block in message.content:
                    if block.type == "tool_use":
                        on_tool(block.name, block.input)
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                self.messages.append(tool_response)

        if last is None:
            raise TurnFailed("لم يصل ردّ من الخادم.")
        return "".join(b.text for b in last.content if b.type == "text")

    def reset(self) -> None:
        self.messages.clear()
