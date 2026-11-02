"""
HR bulk screening routes: upload many resumes (or a ZIP), score them against a
role or job description, review a ranked list, export to CSV.
"""
import csv
import hashlib
import io
import logging
import math
import os
import re
import shutil
import tempfile
import time
import zipfile

from flask import (Blueprint, Response, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

from engine.batch_runner import submit_batch
from engine.screening import build_target

logger = logging.getLogger(__name__)

bp = Blueprint('hr', __name__, url_prefix='/bulk')

BATCH_ID_RE = re.compile(r'^[0-9a-f]{32}$')
RESUME_EXTENSIONS = {'pdf', 'docx'}
STALE_SECONDS = 600       # a "processing" batch with no progress for this long is interrupted
PAGE_SIZE = 50
DECISIONS = {'Strong Hire', 'Consider', 'Reject'}
CSV_DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def services() -> dict:
    return current_app.extensions['hiring']


# ---------------------------------------------------------------- helpers

def _ext(filename: str) -> str:
    return filename.rsplit('.', 1)[1].lower() if filename and '.' in filename else ''


def _display_name(name: str) -> str:
    base = os.path.basename((name or '').replace('\\', '/')).strip()
    return (base or 'resume')[:120]


def _csv_safe(value):
    """Stop spreadsheet formula injection from resume-supplied text."""
    if isinstance(value, str) and value.startswith(CSV_DANGEROUS_PREFIXES):
        return "'" + value
    return value


class _UploadCollector:
    """Saves accepted resumes into a temp folder and tracks what was rejected."""

    def __init__(self, tmp_dir: str, config):
        self.tmp_dir = tmp_dir
        self.max_files = config['BULK_MAX_FILES']
        self.max_file_bytes = config['MAX_RESUME_FILE_SIZE']
        self.max_total_bytes = config['BULK_MAX_TOTAL_BYTES']
        self.items = []        # (display_name, path)
        self.rejected = []     # (display_name, reason)
        self.duplicates = 0
        self.ignored = 0       # beyond the file limit
        self.total_bytes = 0
        self._hashes = set()
        self._counter = 0

    @property
    def count(self) -> int:
        return len(self.items) + len(self.rejected)

    @property
    def full(self) -> bool:
        return self.count >= self.max_files or self.total_bytes >= self.max_total_bytes

    def add(self, display_name: str, ext: str, stream):
        if self.full:
            self.ignored += 1
            return
        data = stream.read(self.max_file_bytes + 1)
        if len(data) > self.max_file_bytes:
            limit_mb = self.max_file_bytes / (1024 * 1024)
            self.rejected.append((display_name, f'File is larger than {limit_mb:g}MB'))
            return
        if not data:
            self.rejected.append((display_name, 'File is empty'))
            return
        digest = hashlib.sha256(data).hexdigest()
        if digest in self._hashes:
            self.duplicates += 1
            return
        self._hashes.add(digest)
        self._counter += 1
        path = os.path.join(self.tmp_dir, f'{self._counter:05d}.{ext}')
        with open(path, 'wb') as f:
            f.write(data)
        self.total_bytes += len(data)
        self.items.append((display_name, path))

    def add_zip(self, display_name: str, stream):
        try:
            archive = zipfile.ZipFile(stream)
        except zipfile.BadZipFile:
            self.rejected.append((display_name, 'Not a valid ZIP file'))
            return
        with archive:
            for info in archive.infolist():
                member = info.filename
                if (info.is_dir() or member.startswith('__MACOSX')
                        or os.path.basename(member).startswith('.')):
                    continue
                ext = _ext(member)
                if ext not in RESUME_EXTENSIONS:
                    continue  # ignore non-resume files inside the archive
                member_name = _display_name(member)
                try:
                    with archive.open(info) as member_stream:
                        self.add(member_name, ext, member_stream)
                except (RuntimeError, zipfile.BadZipFile, NotImplementedError):
                    self.rejected.append((member_name, 'Could not read file in ZIP (encrypted or corrupt)'))


def _load_batch_or_404(batch_id: str) -> dict:
    if not BATCH_ID_RE.match(batch_id):
        abort(404)
    batch = services()['store'].get_batch(batch_id)
    if batch is None:
        abort(404)
    if (batch['status'] == 'processing'
            and time.time() - batch['updated_at'] > STALE_SECONDS):
        batch['status'] = 'interrupted'
    return batch


def _progress_percent(batch: dict) -> int:
    return int(100 * batch['done'] / batch['total']) if batch['total'] else 100


def _remember_batch(batch_id: str):
    recent = [b for b in session.get('batches', []) if b != batch_id]
    session['batches'] = ([batch_id] + recent)[:10]


# ----------------------------------------------------------------- routes

@bp.route('', methods=['GET', 'POST'])
def bulk_form():
    """Upload form (GET) and batch creation (POST)."""
    svc = services()
    config = current_app.config
    pipeline = svc['get_pipeline']()
    roles = sorted(j['role'] for j in pipeline.resume_matcher.jobs_data)

    if request.method == 'GET':
        recent = [svc['store'].get_batch(b) for b in session.get('batches', [])]
        return render_template('bulk.html', roles=roles, form={},
                               recent=[b for b in recent if b],
                               max_files=config['BULK_MAX_FILES'])

    # Raise the size limit for this request only (default applies elsewhere).
    request.max_content_length = config['BULK_MAX_UPLOAD']

    form = {
        'label': request.form.get('label', '').strip()[:80],
        'target_kind': request.form.get('target_kind', 'best_fit'),
        'role': request.form.get('role', ''),
        'jd_text': request.form.get('jd_text', ''),
    }

    def fail(message, status=400):
        flash(message, 'error')
        recent = [svc['store'].get_batch(b) for b in session.get('batches', [])]
        return render_template('bulk.html', roles=roles, form=form,
                               recent=[b for b in recent if b],
                               max_files=config['BULK_MAX_FILES']), status

    matcher = pipeline.resume_matcher
    if matcher.vectorizer is None or matcher.job_vectors is None:
        matcher._fit_vectorizer()
    try:
        target = build_target(form['target_kind'], pipeline.skill_extractor, matcher,
                              role=form['role'], jd_text=form['jd_text'])
    except ValueError as e:
        return fail(str(e))

    uploads = [f for f in request.files.getlist('resumes') if f and f.filename]
    if not uploads:
        return fail('Please choose at least one resume (PDF, DOCX or a ZIP of them)')

    tmp_dir = tempfile.mkdtemp(prefix='batch_')
    collector = _UploadCollector(tmp_dir, config)
    try:
        for upload in uploads:
            name = _display_name(upload.filename)
            ext = _ext(upload.filename)
            if ext in RESUME_EXTENSIONS:
                collector.add(name, ext, upload.stream)
            elif ext == 'zip':
                collector.add_zip(name, upload.stream)
            else:
                collector.rejected.append((name, 'Unsupported file type (use PDF, DOCX or ZIP)'))
    except Exception:
        logger.exception("Error while reading uploads")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return fail('Could not read the uploaded files', 400)

    if collector.count == 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return fail('No PDF or DOCX resumes were found in the upload')

    store = svc['store']
    store.purge_older_than(config['RETENTION_DAYS'])
    label = form['label'] or time.strftime('Batch %Y-%m-%d %H:%M')
    jd_text = form['jd_text'][:20000] if form['target_kind'] == 'jd' else None
    batch_id = store.create_batch(label, target['kind'], target['label'], jd_text,
                                  total=collector.count, duplicates=collector.duplicates)
    for name, reason in collector.rejected:
        store.add_candidate(batch_id, name, status='error', error=reason, name=name)

    if collector.items:
        components = {'extractor': pipeline.skill_extractor, 'matcher': matcher,
                      'scorer': pipeline.hiring_scorer}
        submit_batch(store, batch_id, collector.items, target, components,
                     svc['parse_file'], tmp_dir)
    else:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        store.finish_batch(batch_id, 'done')

    notes = []
    if collector.duplicates:
        notes.append(f'{collector.duplicates} duplicate file(s) skipped')
    if collector.ignored:
        notes.append(f'{collector.ignored} file(s) over the limit were ignored')
    if notes:
        flash('; '.join(notes), 'info')

    _remember_batch(batch_id)
    return redirect(url_for('hr.view', batch_id=batch_id))


@bp.route('/<batch_id>')
def view(batch_id):
    """Ranked results for a batch, with filters and paging."""
    batch = _load_batch_or_404(batch_id)
    store = services()['store']

    q = request.args.get('q', '').strip()[:100]
    decision = request.args.get('decision', '')
    if decision not in DECISIONS:
        decision = ''
    try:
        min_score_pct = min(max(float(request.args.get('min_score', 0) or 0), 0), 100)
    except ValueError:
        min_score_pct = 0
    must_have_raw = request.args.get('must_have', '')[:300]
    must_have = [s.strip().lower() for s in must_have_raw.split(',') if s.strip()][:10]
    sort = request.args.get('sort', 'score')
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except ValueError:
        page = 1

    rows, total = store.list_candidates(
        batch_id, q=q, decision=decision, min_score=min_score_pct / 100.0,
        must_have=must_have, sort=sort, limit=PAGE_SIZE,
        offset=(page - 1) * PAGE_SIZE)
    pages = max(math.ceil(total / PAGE_SIZE), 1)

    filters = {'q': q, 'decision': decision, 'min_score': min_score_pct or '',
               'must_have': must_have_raw, 'sort': sort}
    _remember_batch(batch_id)
    return render_template(
        'batch.html', batch=batch, rows=rows, total=total, page=page, pages=pages,
        page_size=PAGE_SIZE, filters=filters, stats=store.stats(batch_id),
        percent=_progress_percent(batch),
        rank_offset=(page - 1) * PAGE_SIZE)


@bp.route('/<batch_id>/status')
def status(batch_id):
    """Progress as JSON (polled by the results page while processing)."""
    batch = _load_batch_or_404(batch_id)
    return {
        'status': batch['status'], 'total': batch['total'], 'done': batch['done'],
        'failed': batch['failed'], 'percent': _progress_percent(batch),
    }


@bp.route('/<batch_id>/candidate/<int:candidate_id>')
def candidate(batch_id, candidate_id):
    """One candidate: skills, gaps, questions to ask, and a roadmap."""
    batch = _load_batch_or_404(batch_id)
    svc = services()
    person = svc['store'].get_candidate(batch_id, candidate_id)
    if person is None:
        abort(404)

    questions = {}
    roadmap = None
    if person['status'] == 'ok':
        questions = svc['interview_questions'](person['matched'])
        library = svc['roadmaps']
        base = library.recommend_for_role(person['role']) or library.recommend_for_gaps(person['missing'])
        if base:
            roadmap = library.personalize(base, person['skills'])
    return render_template('candidate.html', batch=batch, person=person,
                           questions=questions, roadmap=roadmap)


@bp.route('/<batch_id>/export.csv')
def export_csv(batch_id):
    """Download the full ranked list (ignores page filters)."""
    batch = _load_batch_or_404(batch_id)
    rows = services()['store'].all_candidates(batch_id)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['Rank', 'Name', 'Email', 'Score %', 'Decision', 'Scored against',
                     'Skill match %', 'Matched skills', 'Missing skills', 'All skills',
                     'File', 'Status', 'Error'])
    rank = 0
    for r in rows:
        ok = r['status'] == 'ok'
        if ok:
            rank += 1
        writer.writerow([_csv_safe(v) for v in [
            rank if ok else '', r['name'] or '', r['email'] or '',
            round(r['score'] * 100, 1) if ok and r['score'] is not None else '',
            r['decision'] or '', r['role'] or '',
            r['match_pct'] if ok else '',
            ', '.join(r['matched']), ', '.join(r['missing']), ', '.join(r['skills']),
            r['filename'], r['status'], r['error'] or '']])

    safe_label = re.sub(r'[^A-Za-z0-9_-]+', '_', batch['label']).strip('_') or 'screening'
    return Response(
        out.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{safe_label}.csv"'})


@bp.route('/<batch_id>/delete', methods=['POST'])
def delete(batch_id):
    """Permanently delete a batch and its results."""
    _load_batch_or_404(batch_id)
    services()['store'].delete_batch(batch_id)
    session['batches'] = [b for b in session.get('batches', []) if b != batch_id]
    flash('Batch deleted', 'info')
    return redirect(url_for('hr.bulk_form'))
