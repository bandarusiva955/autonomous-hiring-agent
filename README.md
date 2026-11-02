# Autonomous AI Hiring Agent

A resume analysis web app that parses a resume (PDF or DOCX), extracts skills, matches the candidate to job roles, finds skill gaps, and produces an evaluation report with learning resources and interview questions.

> **Status:** v1 is a classical NLP/ML pipeline (TF-IDF + cosine similarity + graph modeling). It does **not** call an LLM. A multi-agent LLM layer (LangGraph/CrewAI) and embedding-based matching are planned for v2 — see the [Roadmap](#roadmap).

## Features

- **Single resume analysis**: upload one PDF/DOCX, get skills, best-fit roles, gaps, learning resources, interview questions and a suggested roadmap
- **HR bulk screening** (`/bulk`): upload hundreds of resumes at once (many files or a ZIP), rank them against a built-in role, your own pasted job description, or "best fit", then filter, review and export
- **Career assistant chatbot**: floating chat on every page that answers from your own analysis (skill gaps, roadmaps, interview questions, resume tips). Works with no setup; set `ANTHROPIC_API_KEY` to let it answer open-ended questions with Claude (it falls back to the built-in answers if the API is unavailable)
- **Chrome extension** (`extension/`): one click on any job page shows your match %, missing skills and a roadmap, with a chat box. See [extension/README.md](extension/README.md)
- **Career roadmaps** (`/roadmaps`): 8 step-by-step learning paths that show your progress when you enter the skills you already have

## What it does

1. **Parse** a PDF or DOCX resume into text
2. **Extract skills** against a 626-skill database across 20 categories
3. **Match roles** with TF-IDF vectors and cosine similarity against 30 job profiles
4. **Model relationships** as a candidate-skill-job graph with NetworkX
5. **Score** the candidate (Strong Hire / Consider / Reject) from skill match, skill count, technical ratio and critical-skill coverage
6. **Report** skill gaps (core skills first), learning resources and interview questions

## Tech stack

Python, Flask, scikit-learn, NetworkX, PyPDF2, python-docx, gunicorn, pytest, Docker

## Project structure

```
app.py                  Flask app factory, routes, interview question bank
config.py               Settings (dev / production)
data/
  resume_parser.py      PDF and DOCX text extraction
  skills_master.json    Skills database
  jobs.json             Job profiles (core + secondary skills)
  learning_resources.json
  roadmaps.json
engine/
  pipeline.py           Orchestrates the full analysis
  skill_extractor.py    Skill extraction
  resume_matcher.py     TF-IDF + cosine similarity matching
  hiring_scorer.py      Scoring and hiring decision
  graph_builder.py      NetworkX graph
  screening.py          Scoring against a role / job description
  store.py              SQLite storage for batches
  batch_runner.py       Background batch processing
  roadmaps.py           Roadmap loading and personalization
  chatbot.py            Chatbot (built-in answers + optional Claude)
templates/              HTML templates
static/                 CSS
routes_hr.py            Bulk screening routes
routes_roadmaps.py      Roadmap routes
routes_chat.py          Chat and job-match JSON API
extension/              Chrome extension (Manifest V3)
tests/                  pytest suite
docs/sample_report.html Example output
Dockerfile
```

## HR bulk screening

1. Open **HR bulk screening**, choose what you are hiring for: *Best fit*, *A specific role* (31 built-in roles) or *My job description* (paste a JD; skills in it become the requirements).
2. Select many PDF/DOCX files or a ZIP. Up to 500 resumes per batch; duplicates are detected and skipped; unreadable files are listed instead of stopping the batch.
3. Processing runs in the background with a progress bar (about 30 ms per resume in testing, so 300 resumes take roughly 10 seconds).
4. Review the ranked list: search by name/email, require skills (`python, sql`), set a minimum score, filter by decision, sort, and page through results. Open any candidate for matched/missing skills and questions to verify claimed skills.
5. **Export CSV** for your ATS or spreadsheet, or **delete** the batch.

Limits are in `config.py` (`BULK_MAX_FILES`, `BULK_MAX_UPLOAD`, `RETENTION_DAYS`). Only names, emails, skills and scores are stored (SQLite); resume files are deleted after processing, and batches are purged after 30 days.

> Scores are a screening aid based on keyword skill matching and text similarity. They do not evaluate experience quality or fit, and should not be the sole basis for rejecting anyone.

## Chatbot and extension API

- `POST /api/chat` with `{"message": "...", "context": {"skills": [], "missing": [], "role": ""}, "history": []}` returns `{"reply", "links", "suggestions", "source"}`. Limited to 20 messages per minute per IP.
- `POST /api/match-jd` with `{"skills": [...], "jd_text": "..."}` returns the match percentage, matched/missing skills and a suggested roadmap. Limited to 60 per minute per IP.
- The Chrome extension origin is allowed by CORS automatically; add your own site with `CORS_ORIGINS=https://site1,https://site2`.
- Set `ANTHROPIC_API_KEY` (and optionally `CHAT_MODEL`) to enable LLM answers. The key stays on the server. Chat calls cost money, so keep the rate limit on, and if you run several servers use a shared limiter (for example Redis).

## Roadmaps

`data/roadmaps.json` defines the roadmaps (Agentic AI Engineer, Python Backend, Data Analyst, Data Scientist/ML, Data Engineer, DevOps/Cloud, Full Stack, Frontend). Each has stages, topics, a project per stage and official docs. Add a new one by appending to the JSON; `pytest` checks that stage weeks add up and roles exist. API: `GET /api/roadmaps`.

## Run locally

```bash
git clone https://github.com/bandarusiva955/autonomous-hiring-agent.git
cd autonomous-hiring-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

FLASK_ENV=development python app.py                 # http://127.0.0.1:5000
```

Windows PowerShell: `$env:FLASK_ENV="development"; python app.py`

**Windows, one step:** `powershell -ExecutionPolicy Bypass -File .\setup.ps1` creates the virtual environment, installs dependencies, checks they load, and starts the app. Keep the project outside OneDrive (for example `C:\dev`) - OneDrive sync can corrupt virtual environments.

## Run with Docker

```bash
docker build -t hiring-agent .
docker run -p 8000:8000 -e SECRET_KEY=change-me -v hiring-data:/app/instance hiring-agent
# http://localhost:8000
```

## API

```bash
curl -F "resume_file=@resume.pdf" -F "candidate_name=Siva" http://localhost:8000/api/analyze
```

Returns JSON with extracted skills, job matches, hiring score, skill gaps, learning recommendations and interview questions. Other routes: `GET /health`, `/skills`, `/jobs`.

## Privacy and security notes

- Uploaded resumes are parsed from a temporary file that is deleted immediately; nothing is stored.
- Single-resume uploads are limited to 10 MB and to `.pdf` / `.docx`; bulk uploads accept `.pdf`, `.docx` and `.zip`. CSV exports neutralize spreadsheet formulas.
- Set `SECRET_KEY` in production. Debug mode is off unless `FLASK_ENV=development` and `FLASK_DEBUG=1`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Known limitations

- Skill extraction is keyword-based, so it can miss synonyms and context
- Scanned/image-only PDFs are not supported (no OCR)
- Job profiles and the skills list are static JSON files
- Interview questions come from a fixed question bank
- Bulk batches run in-process: a server restart mid-batch leaves it marked *interrupted* (partial results are kept)
- Single-server design (SQLite); for several servers or very large volumes, move to PostgreSQL and a job queue

## Roadmap

- [ ] Embedding-based semantic matching, evaluated against the TF-IDF baseline on a labeled resume set
- [x] Chatbot with optional LLM mode
- [x] Chrome extension MVP
- [ ] LLM agents (resume parser, JD analyzer, matcher, interview coach) orchestrated with LangGraph or CrewAI
- [ ] Deployed live demo
- [ ] Accounts, a free/Pro plan and payments; Chrome Web Store listing

## License

Educational and research use.
