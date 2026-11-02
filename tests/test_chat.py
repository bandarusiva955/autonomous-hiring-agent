"""Tests for the chatbot, /api/chat, /api/match-jd and CORS for the extension."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from engine.chatbot import RateLimiter, sanitize_context, sanitize_history  # noqa: E402

CONTEXT = {"role": "Backend Developer", "skills": ["python", "sql", "git"],
           "missing": ["docker", "fastapi"], "matched": ["python"], "match_pct": 55}

JD = ("We are hiring a backend engineer: Python, FastAPI, PostgreSQL, Docker and AWS experience required. "
      "Testing with pytest and Git.")


@pytest.fixture()
def app(tmp_path):
    return create_app("development", {"DATABASE": str(tmp_path / "t.db"), "TESTING": True,
                                      "ANTHROPIC_API_KEY": None})


@pytest.fixture()
def client(app):
    return app.test_client()


def ask(client, message, context=CONTEXT, history=None):
    return client.post("/api/chat", json={"message": message, "context": context, "history": history or []})


def test_chat_intents(client):
    gaps = ask(client, "What skills am I missing?").get_json()
    assert "docker" in gaps["reply"] and gaps["source"] == "rules"

    roadmap = ask(client, "Give me a roadmap for backend").get_json()
    assert "Backend" in roadmap["reply"] and roadmap["links"][0]["url"].startswith("/roadmaps/")

    interview = ask(client, "interview questions on python").get_json()
    assert "Python" in interview["reply"]

    tips = ask(client, "how do I get shortlisted").get_json()
    assert "ATS" in tips["reply"]

    assert ask(client, "hello").get_json()["suggestions"]
    assert ask(client, "zzzz qqqq").get_json()["suggestions"]


def test_chat_without_context_is_honest(client):
    reply = ask(client, "what skills am I missing", context=None).get_json()["reply"]
    assert "don't have your skills" in reply


def test_chat_input_validation(client):
    assert client.post("/api/chat", json={}).status_code == 400
    assert client.post("/api/chat", json={"message": "   "}).status_code == 400
    assert client.post("/api/chat", json={"message": "x" * 501}).status_code == 400
    assert client.post("/api/chat", data="not json", content_type="text/plain").status_code == 400
    # hostile context must not crash anything
    junk = {"skills": "oops", "missing": [1, None, {"a": 1}], "role": 5, "match_pct": "high"}
    assert ask(client, "what am I missing", context=junk).status_code == 200


def test_chat_rate_limit(app):
    app.extensions["hiring"]["chat_limiter"] = RateLimiter(3)
    client = app.test_client()
    codes = [ask(client, "hi").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_llm_mode_and_fallback(app, monkeypatch):
    bot = app.extensions["hiring"]["chatbot"]
    bot.api_key = "test-key"
    seen = {}

    def fake_llm(message, ctx, turns):
        seen.update(message=message, ctx=ctx, turns=turns)
        return "LLM says hi"

    monkeypatch.setattr(bot, "_call_llm", fake_llm)
    client = app.test_client()
    data = ask(client, "tell me something", history=[{"role": "user", "content": "a"},
                                                      {"role": "assistant", "content": "b"}]).get_json()
    assert data["reply"] == "LLM says hi" and data["source"] == "llm"
    assert seen["ctx"]["skills"] == ["python", "sql", "git"]
    assert len(seen["turns"]) == 2

    def broken(*args):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(bot, "_call_llm", broken)
    fallback = ask(client, "what skills am I missing").get_json()
    assert fallback["source"] == "rules" and "docker" in fallback["reply"]


def test_llm_request_shape(app, monkeypatch):
    """The Claude API request carries the key, model, context and alternating turns."""
    import json
    import urllib.request

    bot = app.extensions["hiring"]["chatbot"]
    bot.api_key = "sk-test"
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"content": [{"type": "text", "text": "ok"}]}).encode()

    def fake_urlopen(request, timeout=None):
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    turns = sanitize_history([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    assert bot._call_llm("question", sanitize_context(CONTEXT), turns) == "ok"
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert captured["body"]["model"] == "claude-sonnet-5-5"
    assert "docker" in captured["body"]["system"]
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["user", "assistant", "user"]


def test_sanitizers():
    assert sanitize_context("x") == {}
    ctx = sanitize_context({"skills": ["a"] * 500, "role": "r" * 500})
    assert len(ctx["skills"]) == 80 and len(ctx["role"]) == 80
    history = sanitize_history([{"role": "assistant", "content": "first"}, {"role": "user", "content": "u1"},
                                {"role": "user", "content": "u2"}, "junk", {"role": "system", "content": "x"}])
    assert [h["role"] for h in history] == ["user"] and history[0]["content"] == "u2"


def test_match_jd(client):
    response = client.post("/api/match-jd", json={"skills": ["Python", "git", "docker"], "jd_text": JD})
    assert response.status_code == 200
    data = response.get_json()
    assert {"python", "git", "docker"} <= {s.lower() for s in data["matched"]}
    assert "fastapi" in [s.lower() for s in data["missing"]]
    assert 0 < data["match_percentage"] < 100
    assert data["verdict"] in {"Strong match", "Good match", "Low match"}
    assert data["roadmap"]["url"].startswith("/roadmaps/")


def test_match_jd_validation(client):
    post = client.post
    assert post("/api/match-jd", json={"skills": [], "jd_text": JD}).status_code == 400
    assert post("/api/match-jd", json={"jd_text": JD}).status_code == 400
    assert post("/api/match-jd", json={"skills": ["python"], "jd_text": "short"}).status_code == 400
    assert post("/api/match-jd", json={"skills": ["python"], "jd_text": 5}).status_code == 400
    blank = post("/api/match-jd", json={"skills": ["python"], "jd_text": "Lovely weather today, we enjoy long walks on the beach."})
    assert blank.status_code == 400 and "recognizable skills" in blank.get_json()["error"]


def test_cors_for_extension(client, app):
    headers = {"Origin": "chrome-extension://abcdefghijklmnop"}
    response = client.post("/api/match-jd", json={"skills": ["python"], "jd_text": JD}, headers=headers)
    assert response.headers["Access-Control-Allow-Origin"] == headers["Origin"]
    preflight = client.options("/api/chat", headers={**headers, "Access-Control-Request-Method": "POST"})
    assert preflight.status_code in (200, 204)
    assert "Content-Type" in preflight.headers["Access-Control-Allow-Headers"]
    # unknown website origins get no CORS access
    other = client.post("/api/match-jd", json={"skills": ["python"], "jd_text": JD},
                        headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in other.headers
    app.config["CORS_ORIGINS"] = ["https://my-site.example"]
    allowed = client.post("/api/match-jd", json={"skills": ["python"], "jd_text": JD},
                          headers={"Origin": "https://my-site.example"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://my-site.example"


def test_chat_widget_is_served_on_pages(client):
    for path in ("/", "/bulk", "/roadmaps"):
        assert b"chat.js" in client.get(path).data
    assert client.get("/static/chat.js").status_code == 200
