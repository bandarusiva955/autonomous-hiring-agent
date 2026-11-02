"""
Roadmap routes: browse learning roadmaps and see them personalized to a skill list.
"""
from flask import Blueprint, abort, current_app, jsonify, render_template, request

bp = Blueprint('roadmaps', __name__)

MAX_SKILLS_IN_QUERY = 100


def library():
    return current_app.extensions['hiring']['roadmaps']


@bp.route('/roadmaps')
def index():
    """All roadmaps."""
    return render_template('roadmaps.html', roadmaps=library().all())


@bp.route('/roadmaps/<slug>')
def detail(slug):
    """One roadmap; add ?skills=python,sql to see your progress on it."""
    roadmap = library().get(slug)
    if roadmap is None:
        abort(404)
    raw = request.args.get('skills', '')[:3000]
    skills = [s.strip() for s in raw.split(',') if s.strip()][:MAX_SKILLS_IN_QUERY]
    personalized = library().personalize(roadmap, skills)
    return render_template('roadmap_detail.html', roadmap=personalized,
                           skills_text=', '.join(skills), has_skills=bool(skills))


@bp.route('/api/roadmaps')
def api_index():
    """Roadmap summaries as JSON."""
    return jsonify([
        {'slug': r['slug'], 'title': r['title'], 'summary': r['summary'],
         'duration_weeks': r['duration_weeks'], 'level': r['level'], 'roles': r['roles']}
        for r in library().all()])
