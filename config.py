"""
Configuration settings for the AI Hiring Agent.

Environment variables:
    FLASK_ENV    development | production   (default: production)
    SECRET_KEY   required in production
    FLASK_DEBUG  1 to enable debug mode (development only)
"""
import os


class Config:
    """Base configuration class."""
    # Flask settings
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Deployment behind a reverse proxy (Render, Railway, nginx, ...): set TRUST_PROXY=1 so the
    # real visitor IP (used by rate limits) and https scheme are read from X-Forwarded-* headers.
    # Only enable it when a trusted proxy is really in front, otherwise clients can fake their IP.
    TRUST_PROXY = os.environ.get('TRUST_PROXY', '0') == '1'
    SESSION_COOKIE_SECURE = os.environ.get('COOKIE_SECURE', '0') == '1'   # set to 1 when served over https
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # File upload settings
    MAX_RESUME_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    # Flask enforces this one (returns 413 when exceeded)
    MAX_CONTENT_LENGTH = MAX_RESUME_FILE_SIZE
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}

    # Bulk (HR) screening
    BULK_MAX_FILES = int(os.environ.get('BULK_MAX_FILES', 500))   # resumes per batch
    BULK_MAX_UPLOAD = 300 * 1024 * 1024          # request size limit for /bulk
    BULK_MAX_TOTAL_BYTES = 500 * 1024 * 1024     # total resume bytes per batch (incl. ZIP contents)
    RETENTION_DAYS = 30                          # batches older than this are purged
    MAX_FORM_PARTS = 2000                        # allow many files in one upload
    # Chatbot: works without a key (built-in answers); set ANTHROPIC_API_KEY for open-ended LLM answers
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    CHAT_MODEL = os.environ.get('CHAT_MODEL', 'claude-sonnet-5-5')
    CHAT_RATE_LIMIT = 20                         # chat messages per minute per IP
    MATCH_RATE_LIMIT = 60                        # job checks per minute per IP
    CORS_ORIGINS = [o for o in os.environ.get('CORS_ORIGINS', '').split(',') if o]  # chrome-extension:// is always allowed
    DATABASE = os.environ.get('DATABASE_PATH')   # defaults to <instance>/screening.db

    # TF-IDF settings
    TFIDF_MAX_FEATURES = 5000
    TFIDF_MIN_DF = 1
    TFIDF_MAX_DF = 0.95

    # Cosine similarity threshold
    SIMILARITY_THRESHOLD = 0.3

    # Hiring decision thresholds
    STRONG_HIRE_THRESHOLD = 0.75
    CONSIDER_THRESHOLD = 0.45
    REJECT_THRESHOLD = 0.0

    # Graph settings
    GRAPH_SIMILARITY_EDGE_THRESHOLD = 0.3

    # Scoring weights
    SCORING_WEIGHTS = {
        'skill_match': 0.35,
        'skill_count': 0.15,
        'technical_ratio': 0.20,
        'critical_skills': 0.30
    }

    # Learning recommendations
    MAX_LEARNING_RECOMMENDATIONS = 10
    MAX_SKILL_GAPS = 5

    # Data file paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SKILLS_FILE = os.path.join(BASE_DIR, 'data', 'skills_master.json')
    JOBS_FILE = os.path.join(BASE_DIR, 'data', 'jobs.json')
    LEARNING_FILE = os.path.join(BASE_DIR, 'data', 'learning_resources.json')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-secret-key')


class ProductionConfig(Config):
    """Production configuration (SECRET_KEY must be set)."""
    DEBUG = False


# Configuration dictionary for easy switching
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
