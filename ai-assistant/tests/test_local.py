"""Standalone (Ollama) engine and server, tested against a fake Ollama API."""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from khabeer.local import agent as local_agent
from khabeer.local.agent import LocalKhabeer, OllamaError, run_tool


class FakeOllama:
    """Serves queued /api/chat replies and records each request body."""

    def __init__(self):
        self.replies: list[tuple[int, dict]] = []
        self.requests: list[dict] = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                fake.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                status, body = fake.replies.pop(0)
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reply(self, content="", tool_calls=None, status=200, error=None):
        body = {"error": error} if error else {
            "message": {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
            "done": True,
        }
        self.replies.append((status, body))


@pytest.fixture
def ollama():
    f = FakeOllama()
    yield f
    f.server.shutdown()


def call(name, args):
    return {"function": {"name": name, "arguments": args}}


def test_tool_call_then_answer(ollama):
    ollama.reply(tool_calls=[call("calculate_vat", {"amount": 1000, "rate_percent": 15})])
    ollama.reply("<think>حساب</think>الضريبة 150")
    bot = LocalKhabeer(model="test-model", base_url=ollama.url)
    seen = []
    result = bot.ask("كم ضريبة 1000؟", on_tool=lambda n, a: seen.append(n))

    assert result == {"answer": "الضريبة 150", "files": []}
    assert seen == ["calculate_vat"]
    first = ollama.requests[0]
    assert first["model"] == "test-model" and first["stream"] is False
    assert {t["function"]["name"] for t in first["tools"]} == set(local_agent.HANDLERS)
    tool_msg = ollama.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and json.loads(tool_msg["content"])["vat"] == 150.0
    assert [m["role"] for m in bot.messages] == ["system", "user", "assistant", "tool", "assistant"]


def test_save_file_writes_inside_output_dir(ollama, tmp_path, monkeypatch):
    monkeypatch.setattr(local_agent, "OUTPUT_DIR", tmp_path)
    ollama.reply(tool_calls=[call("save_file", {"filename": "site/index.html", "content": "<h1>hi</h1>"})])
    ollama.reply("جاهز")
    result = LocalKhabeer(base_url=ollama.url).ask("صمّم صفحة")
    assert result["files"] == [str(tmp_path / "site" / "index.html")]
    assert (tmp_path / "site" / "index.html").read_text() == "<h1>hi</h1>"


def test_missing_model_rolls_back(ollama):
    ollama.reply(status=404, error="model 'x' not found")
    bot = LocalKhabeer(model="x", base_url=ollama.url)
    with pytest.raises(OllamaError, match="ollama pull x"):
        bot.ask("سلام")
    assert len(bot.messages) == 1  # only the system prompt


def test_ollama_not_running():
    bot = LocalKhabeer(base_url="http://127.0.0.1:9")
    with pytest.raises(OllamaError, match="لا يعمل"):
        bot.ask("سلام")


def test_run_tool_is_forgiving():
    assert json.loads(run_tool("calculate_vat", '{"amount": 100, "rate_percent": 15}'))["vat"] == 15.0
    assert "error" in json.loads(run_tool("calculate_vat", {"amount": 100}))  # missing arg
    assert "error" in json.loads(run_tool("calculate_vat", "not json"))
    assert "error" in json.loads(run_tool("nope", {}))
    assert "error" in json.loads(run_tool("save_file", {"filename": "../x", "content": "x"}))


def test_server_end_to_end(ollama, monkeypatch, tmp_path):
    from khabeer.local import server

    monkeypatch.setattr(local_agent, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "LocalKhabeer", lambda: LocalKhabeer(base_url=ollama.url))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    monkeypatch.setattr(server, "PORT", httpd.server_port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"

    def post(path, payload, origin=None):
        req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", **({"Origin": origin} if origin else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    ollama.reply(tool_calls=[call("save_file", {"filename": "a.html", "content": "<p>x</p>"})])
    ollama.reply("تم")
    status, data = post("/api/chat", {"session": "s1", "text": "صفحة"}, origin=base)
    assert status == 200
    assert data["answer"] == "تم"
    assert data["tools"][0]["name"] == "save_file"
    assert data["files"] == [{"filename": "a.html", "content": "<p>x</p>"}]

    assert post("/api/chat", {"text": "x"}, origin="https://evil.example")[0] == 403
    assert post("/api/chat", {"session": "s1", "text": ""})[0] == 400

    ollama.reply(status=404, error="model not found")
    status, data = post("/api/chat", {"session": "s1", "text": "سلام"})
    assert status == 503 and "ollama pull" in data["error"]
    httpd.shutdown()
