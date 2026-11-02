"""
Store - SQLite persistence for bulk screening batches.

Only extracted results are stored (name, email, skills, scores). Resume files
and full resume text are never kept. Batches can be deleted at any time and
are purged automatically after a retention period.
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    status TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_label TEXT NOT NULL,
    jd_text TEXT,
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    name TEXT,
    email TEXT,
    status TEXT NOT NULL,
    error TEXT,
    score REAL,
    decision TEXT,
    role TEXT,
    match_pct REAL,
    similarity REAL,
    skills TEXT,
    matched TEXT,
    missing TEXT
);
CREATE INDEX IF NOT EXISTS idx_candidates_batch_score ON candidates(batch_id, score DESC);
"""

SORT_COLUMNS = {
    'score': 'score DESC, id ASC',
    'name': 'name COLLATE NOCASE ASC, id ASC',
    'match': 'match_pct DESC, id ASC',
}


def _like_escape(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class ScreeningStore:
    """Small SQLite wrapper; one short-lived connection per operation."""

    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------- batches ----------

    def create_batch(self, label: str, target_kind: str, target_label: str,
                     jd_text: Optional[str], total: int, duplicates: int = 0) -> str:
        batch_id = uuid.uuid4().hex
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                'INSERT INTO batches (id, label, created_at, updated_at, status, '
                'target_kind, target_label, jd_text, total, duplicates) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (batch_id, label, now, now, 'processing', target_kind,
                 target_label, jd_text, total, duplicates))
        return batch_id

    def get_batch(self, batch_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        return dict(row) if row else None

    def finish_batch(self, batch_id: str, status: str = 'done'):
        with self._conn() as conn:
            conn.execute('UPDATE batches SET status = ?, updated_at = ? WHERE id = ?',
                         (status, time.time(), batch_id))

    def delete_batch(self, batch_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute('DELETE FROM batches WHERE id = ?', (batch_id,))
            return cur.rowcount > 0

    def purge_older_than(self, days: float) -> int:
        cutoff = time.time() - days * 86400
        with self._conn() as conn:
            cur = conn.execute('DELETE FROM batches WHERE created_at < ?', (cutoff,))
            return cur.rowcount

    # ---------- candidates ----------

    def add_candidate(self, batch_id: str, filename: str, status: str = 'ok',
                      error: Optional[str] = None, name: Optional[str] = None,
                      email: Optional[str] = None, result: Optional[Dict] = None):
        """Insert one candidate and advance the batch progress counters."""
        result = result or {}
        with self._conn() as conn:
            conn.execute(
                'INSERT INTO candidates (batch_id, filename, name, email, status, error, '
                'score, decision, role, match_pct, similarity, skills, matched, missing) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (batch_id, filename, name, email, status, error,
                 result.get('score'), result.get('decision'), result.get('role'),
                 result.get('match_percentage'), result.get('similarity'),
                 json.dumps([s.lower() for s in result.get('skills', [])]),
                 json.dumps(result.get('matched', [])),
                 json.dumps(result.get('missing', []))))
            conn.execute(
                'UPDATE batches SET done = done + 1, failed = failed + ?, updated_at = ? '
                'WHERE id = ?',
                (1 if status != 'ok' else 0, time.time(), batch_id))

    @staticmethod
    def _filters(batch_id: str, q: str, decision: str, min_score: float,
                 must_have: List[str]) -> Tuple[str, list]:
        where = ['batch_id = ?']
        params: list = [batch_id]
        if q:
            where.append("(name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' "
                         "OR filename LIKE ? ESCAPE '\\')")
            like = f'%{_like_escape(q)}%'
            params += [like, like, like]
        if decision:
            where.append('decision = ?')
            params.append(decision)
        if min_score:
            where.append('score >= ?')
            params.append(min_score)
        for skill in must_have:
            where.append("skills LIKE ? ESCAPE '\\'")
            params.append(f'%"{_like_escape(skill.lower())}"%')
        return ' AND '.join(where), params

    def list_candidates(self, batch_id: str, q: str = '', decision: str = '',
                        min_score: float = 0.0, must_have: Optional[List[str]] = None,
                        sort: str = 'score', limit: int = 50,
                        offset: int = 0) -> Tuple[List[Dict], int]:
        """Return (rows, total_matching). Errors are listed after valid rows."""
        where, params = self._filters(batch_id, q, decision, min_score, must_have or [])
        order = SORT_COLUMNS.get(sort, SORT_COLUMNS['score'])
        with self._conn() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM candidates WHERE {where}',
                                 params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM candidates WHERE {where} "
                f"ORDER BY (status != 'ok') ASC, {order} LIMIT ? OFFSET ?",
                params + [limit, offset]).fetchall()
        return [self._row(r) for r in rows], total

    def all_candidates(self, batch_id: str) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE batch_id = ? "
                "ORDER BY (status != 'ok') ASC, score DESC, id ASC",
                (batch_id,)).fetchall()
        return [self._row(r) for r in rows]

    def get_candidate(self, batch_id: str, candidate_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute('SELECT * FROM candidates WHERE batch_id = ? AND id = ?',
                               (batch_id, candidate_id)).fetchone()
        return self._row(row) if row else None

    def stats(self, batch_id: str) -> Dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT decision, COUNT(*) AS n FROM candidates "
                "WHERE batch_id = ? AND status = 'ok' GROUP BY decision",
                (batch_id,)).fetchall()
            avg = conn.execute(
                "SELECT AVG(score) FROM candidates WHERE batch_id = ? AND status = 'ok'",
                (batch_id,)).fetchone()[0]
        counts = {r['decision']: r['n'] for r in rows}
        return {
            'strong_hire': counts.get('Strong Hire', 0),
            'consider': counts.get('Consider', 0),
            'reject': counts.get('Reject', 0),
            'average_score': round(avg, 4) if avg is not None else 0,
        }

    @staticmethod
    def _row(row) -> Dict:
        data = dict(row)
        for key in ('skills', 'matched', 'missing'):
            data[key] = json.loads(data[key]) if data.get(key) else []
        return data
