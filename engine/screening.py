"""
Screening - score many resumes against one target (a role, a pasted job
description, or "best fit" across all roles) and extract contact details.
"""
import logging
import re
from typing import Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_NAME_OK = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,60}$")
_HEADINGS = {
    'resume', 'curriculum vitae', 'cv', 'profile', 'summary', 'objective',
    'contact', 'education', 'experience', 'skills', 'projects',
}

MAX_JD_CHARS = 20000


def extract_contact(text: str, fallback_name: str) -> Dict[str, Optional[str]]:
    """
    Best-effort name and email from resume text.

    The name is the first short, letters-only line near the top (typical
    resume layout); otherwise the file name is used.
    """
    name = None
    for line in [ln.strip() for ln in text.splitlines() if ln.strip()][:6]:
        words = line.split()
        if (2 <= len(words) <= 4 and _NAME_OK.match(line)
                and line.lower() not in _HEADINGS and '@' not in line):
            name = line.title() if line.isupper() else line
            break
    email_match = EMAIL_RE.search(text)
    return {
        'name': name or fallback_name,
        'email': email_match.group(0) if email_match else None,
    }


def build_target(kind: str, extractor, matcher, role: str = None,
                 jd_text: str = None) -> Dict:
    """
    Resolve what candidates are scored against.

    kind:
        'role'      one of the built-in job profiles
        'jd'        a pasted job description
        'best_fit'  whichever built-in role fits each candidate best

    Raises:
        ValueError: with a message safe to show to the user
    """
    if kind == 'role':
        wanted = (role or '').strip().lower()
        job = next((j for j in matcher.jobs_data
                    if j.get('role', '').lower() == wanted), None)
        if job is None:
            raise ValueError('Please choose a valid job role')
        return {'kind': 'role', 'label': job['role'], 'job': job}

    if kind == 'jd':
        jd_text = (jd_text or '').strip()[:MAX_JD_CHARS]
        if len(jd_text) < 30:
            raise ValueError('The job description is too short')
        skills = [s['skill'] for s in extractor.extract_skills(jd_text)]
        if not skills:
            raise ValueError('No recognizable skills were found in the job description')
        vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2),
                                     sublinear_tf=True)
        jd_vector = vectorizer.fit_transform([jd_text])
        job = {
            'role': 'Custom job description',
            'core_skills': skills,
            'secondary_skills': [],
            'description': jd_text,
        }
        return {'kind': 'jd', 'label': 'Custom job description', 'job': job,
                'vectorizer': vectorizer, 'jd_vector': jd_vector}

    if kind == 'best_fit':
        return {'kind': 'best_fit', 'label': 'Best fit across all roles'}

    raise ValueError('Unknown screening target')


def _match_custom_jd(text: str, skills: List[str], target: Dict) -> Dict:
    """Match one resume against a pasted job description."""
    job = target['job']
    resume_skills = {s.lower() for s in skills}
    core = list(dict.fromkeys(job['core_skills']))
    matched = [s for s in core if s.lower() in resume_skills]
    missing = [s for s in core if s.lower() not in resume_skills]

    resume_vector = target['vectorizer'].transform([text[:MAX_JD_CHARS]])
    similarity = float(cosine_similarity(resume_vector, target['jd_vector'])[0][0])

    return {
        'role': job['role'],
        'similarity_score': round(similarity, 4),
        'match_percentage': round(100 * len(matched) / len(core), 2) if core else 0,
        'matched_skills': matched,
        'missing_skills': missing,
        'core_skills': core,
    }


def score_resume(text: str, target: Dict, extractor, matcher, scorer) -> Dict:
    """
    Score one resume against the target.

    Returns a flat dict ready to store: skills, score (0-1), decision, the
    role it was scored against, match percentage, similarity, matched/missing.
    """
    skills = [s['skill'] for s in extractor.extract_skills(text)]

    if target['kind'] == 'jd':
        job_match = _match_custom_jd(text, skills, target)
        result = scorer.calculate_score(skills, job_match)
    else:
        matches = matcher.match_resume(text, skills)
        if not matches:
            raise ValueError('No job profiles are available for matching')
        if target['kind'] == 'role':
            wanted = target['job']['role']
            job_match = next(m for m in matches if m['role'] == wanted)
            result = scorer.calculate_score(skills, job_match)
        else:
            scored = [(scorer.calculate_score(skills, m), m) for m in matches]
            result, job_match = max(scored, key=lambda pair: pair[0]['final_score'])

    return {
        'skills': skills,
        'role': job_match['role'],
        'score': result['final_score'],
        'decision': result['decision'],
        'match_percentage': job_match.get('match_percentage', 0),
        'similarity': job_match.get('similarity_score', 0),
        'matched': job_match.get('matched_skills', []),
        'missing': job_match.get('missing_skills', []),
    }


def match_skills_to_jd(skills: List[str], jd_text: str, extractor) -> Dict:
    """
    Compare a person's skill list with the skills found in a job description.

    Raises:
        ValueError: with a message safe to show to the user
    """
    jd_text = (jd_text or '').strip()[:MAX_JD_CHARS]
    if len(jd_text) < 30:
        raise ValueError('The job description is too short')
    required = list(dict.fromkeys(s['skill'] for s in extractor.extract_skills(jd_text)))
    if not required:
        raise ValueError('No recognizable skills were found on this page')

    have = {s.strip().lower() for s in skills if isinstance(s, str) and s.strip()}
    matched = [s for s in required if s.lower() in have]
    missing = [s for s in required if s.lower() not in have]
    pct = round(100 * len(matched) / len(required))
    if pct >= 70:
        verdict = 'Strong match'
    elif pct >= 40:
        verdict = 'Good match'
    else:
        verdict = 'Low match'
    return {
        'match_percentage': pct,
        'verdict': verdict,
        'required_skills': required,
        'matched': matched,
        'missing': missing,
    }
