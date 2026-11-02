"""Tests for production behavior: proxy headers, secret key sharing, security headers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from engine.chatbot import RateLimiter  # noqa: E402


def make_app(tmp_path, **overrides):
    settings = {"DATABASE": str(tmp_path / "data" / "t.db"), "TESTING": True}
    settings.update(overrides)
    return create_app("production", settings)


def chat(client, ip):
    return client.post("/api/chat", json={"message": "hi"}, headers={"X-Forwarded-For": ip})


def test_rate_limit_uses_real_client_ip_behind_proxy(tmp_path):
    app = make_app(tmp_path, TRUST_PROXY=True)
    app.extensions["hiring"]["chat_limiter"] = RateLimiter(2)
    client = app.test_client()
    assert [chat(client, "10.0.0.1").status_code for _ in range(3)] == [200, 200, 429]
    assert chat(client, "10.0.0.2").status_code == 200      # a different visitor has their own budget


def test_forwarded_header_ignored_without_trust_proxy(tmp_path):
    app = make_app(tmp_path, TRUST_PROXY=False)
    app.extensions["hiring"]["chat_limiter"] = RateLimiter(2)
    client = app.test_client()
    # spoofing X-Forwarded-For must not give a fresh budget
    codes = [chat(client, f"10.0.0.{i}").status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_generated_secret_key_is_shared_between_workers(tmp_path):
    first = make_app(tmp_path, SECRET_KEY=None)
    second = make_app(tmp_path, SECRET_KEY=None)          # a second worker starting later
    assert first.config["SECRET_KEY"] == second.config["SECRET_KEY"]
    assert len(first.config["SECRET_KEY"]) == 64
    key_file = tmp_path / "data" / ".secret_key"
    assert key_file.exists()
    if os.name == "posix":
        assert oct(key_file.stat().st_mode & 0o777) == "0o600"


def test_configured_secret_key_wins(tmp_path):
    app = make_app(tmp_path, SECRET_KEY="from-environment")
    assert app.config["SECRET_KEY"] == "from-environment"
    assert not (tmp_path / "data" / ".secret_key").exists()


def test_security_headers_and_health(tmp_path):
    client = make_app(tmp_path).test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_session_cookie_settings(tmp_path):
    app = make_app(tmp_path)
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
