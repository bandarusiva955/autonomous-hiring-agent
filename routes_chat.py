"""
JSON APIs used by the website chat widget and the Chrome extension:
  POST /api/chat       career chatbot
  POST /api/match-jd   compare a skill list with a job description
"""
import logging
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request

from engine.chatbot import MAX_MESSAGE_CHARS
from engine.screening import match_skills_to_jd

logger = logging.getLogger(__name__)

bp = Blueprint('chat', __name__)

MAX_SKILLS = 200
MAX_SKILL_LEN = 60


def services() -> dict:
    return current_app.extensions['hiring']


def _client_ip() -> str:
    return request.remote_addr or 'unknown'


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.after_app_request
def add_cors_headers(response):
    """Let the Chrome extension (and any configured origin) call /api/*."""
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin', '')
        if origin.startswith('chrome-extension://') or origin in current_app.config['CORS_ORIGINS']:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Max-Age'] = '600'
            response.headers.add('Vary', 'Origin')
    return response


@bp.route('/api/chat', methods=['POST'])
def chat():
    if not services()['chat_limiter'].allow(_client_ip()):
        return jsonify({'error': 'Too many messages. Please wait a minute and try again.'}), 429

    data = _json_body()
    message = data.get('message')
    if not isinstance(message, str) or not message.strip():
        return jsonify({'error': 'Please type a message'}), 400
    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify({'error': f'Message is too long (max {MAX_MESSAGE_CHARS} characters)'}), 400

    result = services()['chatbot'].reply(message, data.get('context'), data.get('history'))
    return jsonify(result)


@bp.route('/api/match-jd', methods=['POST'])
def match_jd():
    """Skills list + job text in, match percentage, gaps and a roadmap out."""
    if not services()['match_limiter'].allow(_client_ip()):
        return jsonify({'error': 'Too many requests. Please wait a minute and try again.'}), 429

    data = _json_body()
    skills = data.get('skills')
    if not isinstance(skills, list) or not skills:
        return jsonify({'error': 'Add your skills first (import a resume or type them in)'}), 400
    skills = [s.strip()[:MAX_SKILL_LEN] for s in skills if isinstance(s, str) and s.strip()][:MAX_SKILLS]
    if not skills:
        return jsonify({'error': 'Add your skills first (import a resume or type them in)'}), 400

    jd_text = data.get('jd_text')
    if not isinstance(jd_text, str):
        return jsonify({'error': 'No job text received'}), 400

    try:
        result = match_skills_to_jd(skills, jd_text, services()['get_extractor']())
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    library = services()['roadmaps']
    base = library.recommend_for_gaps(result['missing'])
    if base:
        plan = library.personalize(base, skills)
        skills_q = quote(','.join(skills[:60]), safe=',')
        result['roadmap'] = {
            'slug': plan['slug'], 'title': plan['title'], 'progress': plan['progress'],
            'next_stage': plan['next_stage'], 'duration_weeks': plan['duration_weeks'],
            'url': f"/roadmaps/{plan['slug']}?skills={skills_q}",
        }
    else:
        result['roadmap'] = None
    return jsonify(result)
