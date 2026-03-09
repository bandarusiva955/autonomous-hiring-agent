"""
Configuration settings for the AI Hiring Agent.
"""
import os

class Config:
    """Base configuration class."""
    # Flask settings
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # File upload settings
    MAX_RESUME_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    
    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
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
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Must be set in production


# Configuration dictionary for easy switching
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

