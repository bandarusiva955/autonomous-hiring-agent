# Autonomous AI Hiring Agent

A resume analysis web app that parses a resume (PDF or DOCX), extracts skills, matches the candidate to job roles, finds skill gaps, and produces an evaluation report with learning resources and interview questions.

> **Status:** v1 is a classical NLP/ML pipeline (TF-IDF + cosine similarity + graph modeling). It does **not** call an LLM. A multi-agent LLM layer (LangGraph/CrewAI) and embedding-based matching are planned for v2 — see the [Roadmap](#roadmap).

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
engine/
  pipeline.py           Orchestrates the full analysis
  skill_extractor.py    Skill extraction
  resume_matcher.py     TF-IDF + cosine similarity matching
  hiring_scorer.py      Scoring and hiring decision
  graph_builder.py      NetworkX graph
templates/              HTML templates
tests/                  pytest suite
docs/sample_report.html Example output
Dockerfile
```

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
docker run -p 8000:8000 -e SECRET_KEY=change-me hiring-agent
# http://localhost:8000
```

## API

```bash
curl -F "resume_file=@resume.pdf" -F "candidate_name=Siva" http://localhost:8000/api/analyze
```

Returns JSON with extracted skills, job matches, hiring score, skill gaps, learning recommendations and interview questions. Other routes: `GET /health`, `/skills`, `/jobs`.

## Privacy and security notes

- Uploaded resumes are parsed from a temporary file that is deleted immediately; nothing is stored.
- Uploads are limited to 10 MB and to `.pdf` / `.docx`.
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

## Roadmap

- [ ] Embedding-based semantic matching, evaluated against the TF-IDF baseline on a labeled resume set
- [ ] LLM agents (resume parser, JD analyzer, matcher, interview coach) orchestrated with LangGraph or CrewAI
- [ ] Paste-a-job-description matching (not only the built-in 30 roles)
- [ ] Deployed live demo
- [ ] Chrome extension that scores the job page you are viewing

## License

Educational and research use.
