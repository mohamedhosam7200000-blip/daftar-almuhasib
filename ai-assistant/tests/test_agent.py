"""Drive the agent loop against a fake API: tool call, then final answer."""

import json

import anthropic
import httpx2
import pytest

from khabeer.agent import Khabeer, TurnFailed


def _msg(content, stop_reason):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _client(responses, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json=responses.pop(0))
    return anthropic.Anthropic(
        api_key="test",
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )


def test_tool_call_then_answer_keeps_history():
    seen = []
    client = _client([
        _msg([{"type": "tool_use", "id": "tu_1", "name": "calculate_vat",
               "input": {"amount": 1000, "rate_percent": 15}}], "tool_use"),
        _msg([{"type": "text", "text": "الضريبة 150"}], "end_turn"),
    ], seen)
    bot = Khabeer(client)
    tools_called = []
    answer = bot.ask("كم ضريبة 1000 بنسبة 15%؟", on_tool=lambda n, a: tools_called.append(n))

    assert answer == "الضريبة 150"
    assert tools_called == ["calculate_vat"]
    assert seen[0]["fallbacks"] == "default"
    assert seen[0]["thinking"] == {"type": "adaptive"}
    tool_result = seen[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert json.loads(tool_result["content"])["vat"] == 150.0
    # user, assistant(tool_use), user(tool_result), assistant(answer)
    assert [m["role"] for m in bot.messages] == ["user", "assistant", "user", "assistant"]


def test_refusal_rolls_back_history():
    seen = []
    client = _client([_msg([], "refusal")], seen)
    bot = Khabeer(client)
    with pytest.raises(TurnFailed):
        bot.ask("...")
    assert bot.messages == []
