"""Tests for HR bulk screening and roadmaps."""
import io
import os
import sys
import time
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    return create_app("development", {"DATABASE": str(tmp_path / "test.db"), "TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


def make_docx(*lines: str) -> bytes:
    import docx

    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


STRONG = make_docx("Asha Rao", "asha@example.com",
                   "Python, SQL, machine learning, statistics, data analysis, pandas, numpy, tableau")
WEAK = make_docx("Ravi Kumar", "ravi@example.com", "Photoshop, illustrator, figma")
FORMULA = make_docx("=HYPERLINK(1)", "evil@example.com", "Python SQL")


def wait_done(app, batch_id, timeout=30):
    store = app.extensions["hiring"]["store"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        batch = store.get_batch(batch_id)
        if batch["status"] != "processing":
            return batch
        time.sleep(0.1)
    raise AssertionError("batch did not finish")


def post_batch(client, files, **fields):
    data = {"target_kind": "role", "role": "Data Scientist", **fields}
    data["resumes"] = files
    response = client.post("/bulk", data=data, content_type="multipart/form-data")
    assert response.status_code == 302, response.data[:300]
    return response.headers["Location"].rstrip("/").rsplit("/", 1)[1]


def test_pages_load(client):
    for path in ("/bulk", "/roadmaps", "/api/roadmaps", "/roadmaps/agentic-ai-engineer"):
        assert client.get(path).status_code == 200


def test_bulk_ranks_candidates(app, client):
    batch_id = post_batch(client, [(io.BytesIO(WEAK), "weak.docx"), (io.BytesIO(STRONG), "strong.docx")])
    batch = wait_done(app, batch_id)
    assert batch["done"] == 2 and batch["failed"] == 0

    rows, total = app.extensions["hiring"]["store"].list_candidates(batch_id)
    assert total == 2
    assert rows[0]["name"] == "Asha Rao"            # strong resume ranks first
    assert rows[0]["email"] == "asha@example.com"
    assert rows[0]["score"] > rows[1]["score"]
    page = client.get(f"/bulk/{batch_id}")
    assert page.status_code == 200 and b"Asha Rao" in page.data


def test_zip_duplicates_and_bad_files(app, client):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("team/a.docx", STRONG)
        z.writestr("team/b.docx", WEAK)
        z.writestr("team/readme.txt", "ignored")
        z.writestr("__MACOSX/team/._a.docx", "junk")
    archive.seek(0)
    batch_id = post_batch(client, [
        (archive, "bundle.zip"),
        (io.BytesIO(STRONG), "same_as_a.docx"),      # duplicate of a.docx content
        (io.BytesIO(b"not a real docx"), "broken.docx"),
        (io.BytesIO(b"png"), "photo.png"),
    ])
    batch = wait_done(app, batch_id)
    assert batch["duplicates"] == 1
    assert batch["total"] == 4          # a, b, broken, photo (txt/macos ignored, duplicate skipped)
    assert batch["failed"] == 2         # broken + unsupported type
    assert batch["status"] == "done"


def test_failed_file_does_not_stop_batch(app, client):
    batch_id = post_batch(client, [(io.BytesIO(b"junk"), "bad.docx"), (io.BytesIO(STRONG), "good.docx")])
    batch = wait_done(app, batch_id)
    assert batch["done"] == 2 and batch["failed"] == 1


def test_file_limit_is_enforced(app, client):
    app.config["BULK_MAX_FILES"] = 2
    files = [(io.BytesIO(make_docx(f"Person {i}", f"Skill python {i}")), f"r{i}.docx") for i in range(5)]
    batch_id = post_batch(client, files)
    batch = wait_done(app, batch_id)
    assert batch["total"] == 2


def test_custom_job_description(app, client):
    jd = "We need a data analyst with strong Python, SQL, tableau and statistics experience for reporting."
    batch_id = post_batch(client, [(io.BytesIO(STRONG), "s.docx"), (io.BytesIO(WEAK), "w.docx")],
                          target_kind="jd", jd_text=jd)
    wait_done(app, batch_id)
    rows, _ = app.extensions["hiring"]["store"].list_candidates(batch_id)
    assert rows[0]["name"] == "Asha Rao"
    assert rows[0]["role"] == "Custom job description"
    assert "python" in rows[0]["matched"]


def test_best_fit_target(app, client):
    batch_id = post_batch(client, [(io.BytesIO(STRONG), "s.docx")], target_kind="best_fit")
    wait_done(app, batch_id)
    rows, _ = app.extensions["hiring"]["store"].list_candidates(batch_id)
    assert rows[0]["role"]


def test_invalid_target_inputs_are_rejected(client):
    files = [(io.BytesIO(STRONG), "s.docx")]
    bad_role = client.post("/bulk", data={"target_kind": "role", "role": "Wizard", "resumes": files},
                           content_type="multipart/form-data")
    assert bad_role.status_code == 400 and b"valid job role" in bad_role.data
    short_jd = client.post("/bulk", data={"target_kind": "jd", "jd_text": "hi",
                                          "resumes": [(io.BytesIO(STRONG), "s.docx")]},
                           content_type="multipart/form-data")
    assert short_jd.status_code == 400
    no_files = client.post("/bulk", data={"target_kind": "best_fit"}, content_type="multipart/form-data")
    assert no_files.status_code == 400


def test_filters(app, client):
    batch_id = post_batch(client, [(io.BytesIO(STRONG), "s.docx"), (io.BytesIO(WEAK), "w.docx")])
    wait_done(app, batch_id)
    store = app.extensions["hiring"]["store"]
    assert store.list_candidates(batch_id, must_have=["python", "sql"])[1] == 1
    assert store.list_candidates(batch_id, must_have=["python", "photoshop"])[1] == 0
    assert store.list_candidates(batch_id, q="ravi")[1] == 1
    assert store.list_candidates(batch_id, q="%")[1] == 0       # wildcard is escaped
    assert client.get(f"/bulk/{batch_id}?must_have=python&min_score=1&sort=name&page=abc").status_code == 200


def test_csv_export_is_safe_and_complete(app, client):
    batch_id = post_batch(client, [(io.BytesIO(FORMULA), "=cmd|calc.docx"), (io.BytesIO(STRONG), "s.docx")])
    wait_done(app, batch_id)
    response = client.get(f"/bulk/{batch_id}/export.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    text = response.data.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Rank,Name,Email")
    assert "'=cmd|calc.docx" in text        # formula neutralised
    assert ",=cmd" not in text
    assert "=HYPERLINK" not in text.split("\n", 1)[1].split(",")[1]   # unsafe name never used as the name


def test_candidate_page_has_questions_and_roadmap(app, client):
    batch_id = post_batch(client, [(io.BytesIO(STRONG), "s.docx")])
    wait_done(app, batch_id)
    row = app.extensions["hiring"]["store"].list_candidates(batch_id)[0][0]
    page = client.get(f"/bulk/{batch_id}/candidate/{row['id']}")
    assert page.status_code == 200
    assert b"Asha Rao" in page.data and b"growth path" in page.data


def test_delete_batch(app, client):
    batch_id = post_batch(client, [(io.BytesIO(STRONG), "s.docx")])
    wait_done(app, batch_id)
    assert client.post(f"/bulk/{batch_id}/delete").status_code == 302
    assert client.get(f"/bulk/{batch_id}").status_code == 404


def test_bad_batch_ids_404(client):
    assert client.get("/bulk/not-a-real-id").status_code == 404
    assert client.get("/bulk/" + "0" * 32).status_code == 404
    assert client.get("/bulk/../../etc/passwd").status_code == 404


def test_old_batches_are_purged(app, client):
    store = app.extensions["hiring"]["store"]
    batch_id = store.create_batch("old", "best_fit", "x", None, total=0)
    with store._conn() as conn:
        conn.execute("UPDATE batches SET created_at = ? WHERE id = ?", (time.time() - 40 * 86400, batch_id))
    assert store.purge_older_than(30) == 1
    assert store.get_batch(batch_id) is None


def test_roadmap_personalization(app, client):
    library = app.extensions["hiring"]["roadmaps"]
    roadmap = library.get("python-backend-developer")
    plan = library.personalize(roadmap, ["Python", "git", "oop", "data structures", "algorithms"])
    assert plan["stages"][0]["status"] == "done"
    assert plan["next_stage"] == plan["stages"][1]["title"]
    assert 0 < plan["progress"] < 100
    assert library.personalize(roadmap, [])["progress"] == 0
    page = client.get("/roadmaps/python-backend-developer?skills=python,git")
    assert page.status_code == 200 and b"Your progress" in page.data
    assert client.get("/roadmaps/nope").status_code == 404


def test_every_roadmap_is_consistent(app):
    library = app.extensions["hiring"]["roadmaps"]
    assert len(library.all()) >= 8
    for roadmap in library.all():
        assert sum(stage["weeks"] for stage in roadmap["stages"]) == roadmap["duration_weeks"], roadmap["slug"]
        for role in roadmap["roles"]:
            assert library.recommend_for_role(role) is not None
