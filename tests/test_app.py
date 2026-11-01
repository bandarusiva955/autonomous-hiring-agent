"""Tests for the Flask routes."""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


@pytest.fixture()
def client():
    app = create_app("development")
    app.config["TESTING"] = True
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1MB keeps the size test fast
    return app.test_client()


def make_docx(text: str) -> io.BytesIO:
    import docx

    document = docx.Document()
    for line in text.strip().splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


RESUME = """
Data analyst skilled in Python, SQL, pandas, numpy, scikit-learn and machine learning.
Experience with data analysis, statistics and Docker.
"""


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_pages_load(client):
    for path in ("/", "/skills", "/jobs"):
        assert client.get(path).status_code == 200


def test_api_analyze_docx(client):
    response = client.post(
        "/api/analyze",
        data={"resume_file": (make_docx(RESUME), "resume.docx"), "candidate_name": "Siva"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["candidate_name"] == "Siva"
    assert "python" in body["extracted_skills"]
    assert body["best_match"]["role"]


def test_api_rejects_bad_extension(client):
    response = client.post(
        "/api/analyze",
        data={"resume_file": (io.BytesIO(b"hello"), "resume.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.get_json()["error"]


def test_api_missing_file(client):
    response = client.post("/api/analyze", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_api_rejects_oversized_upload(client):
    big = io.BytesIO(b"0" * (2 * 1024 * 1024))
    response = client.post(
        "/api/analyze",
        data={"resume_file": (big, "resume.docx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413


def test_html_flow_renders_report(client):
    response = client.post(
        "/analyze",
        data={"resume_file": (make_docx(RESUME), "resume.docx"), "candidate_name": "Siva"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Siva" in response.data


def test_uploaded_resume_is_not_kept(client):
    """Resumes must never be left on disk after analysis."""
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    before = set(os.listdir(app_dir))
    client.post(
        "/api/analyze",
        data={"resume_file": (make_docx(RESUME), "resume.docx")},
        content_type="multipart/form-data",
    )
    assert set(os.listdir(app_dir)) - before <= {"__pycache__", ".pytest_cache"}
