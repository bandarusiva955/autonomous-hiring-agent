"""
AI Hiring Agent - Flask Application
Autonomous AI Hiring Agent using LLM, Machine Learning and Graph-Based Recommendation

This application provides:
- Resume Upload and Parsing
- Skill Extraction using comprehensive skills database
- TF-IDF vectorization and Cosine Similarity matching
- NetworkX graph-based candidate-job relationships
- Hiring decision classification (Strong Hire / Consider / Reject)
- Learning resource recommendations
- Detailed analysis reports
"""

import os
import json
import logging
from pathlib import Path

# Flask imports
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import configuration
from config import config

# Import pipeline components
from engine.pipeline import ResumeProcessingPipeline
from engine.skill_extractor import SkillExtractor
from engine.resume_matcher import ResumeMatcher
from engine.hiring_scorer import HiringScorer
from engine.graph_builder import GraphBuilder

# Import resume parser
from data.resume_parser import extract_text_from_file


def create_app(config_name='default'):
    """Application factory pattern for Flask app."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize pipeline components (lazy loading)
    pipeline = None
    skill_extractor = None
    resume_matcher = None
    hiring_scorer = None
    graph_builder = None
    
    def get_pipeline():
        """Get or initialize the processing pipeline."""
        nonlocal pipeline
        if pipeline is None:
            pipeline = ResumeProcessingPipeline(
                skills_file=app.config['SKILLS_FILE'],
                jobs_file=app.config['JOBS_FILE']
            )
        return pipeline
    
    def get_skill_extractor():
        """Get or initialize skill extractor."""
        nonlocal skill_extractor
        if skill_extractor is None:
            skill_extractor = SkillExtractor(app.config['SKILLS_FILE'])
        return skill_extractor
    
    def get_resume_matcher():
        """Get or initialize resume matcher."""
        nonlocal resume_matcher
        if resume_matcher is None:
            resume_matcher = ResumeMatcher(
                jobs_file=app.config['JOBS_FILE'],
                max_features=app.config['TFIDF_MAX_FEATURES']
            )
        return resume_matcher
    
    def get_hiring_scorer():
        """Get or initialize hiring scorer."""
        nonlocal hiring_scorer
        if hiring_scorer is None:
            hiring_scorer = HiringScorer(
                strong_threshold=app.config['STRONG_HIRE_THRESHOLD'],
                consider_threshold=app.config['CONSIDER_THRESHOLD']
            )
        return hiring_scorer
    
    def get_graph_builder():
        """Get or initialize graph builder."""
        nonlocal graph_builder
        if graph_builder is None:
            graph_builder = GraphBuilder(app.config['JOBS_FILE'])
        return graph_builder
    
    # ==================== Routes ====================
    
    @app.route('/')
    def index():
        """Home page - upload resume."""
        return render_template('index.html')
    
    @app.route('/analyze', methods=['POST'])
    def analyze():
        """Analyze uploaded resume."""
        try:
            # Check if file was uploaded
            if 'resume_file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('index'))
            
            file = request.files['resume_file']
            
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(url_for('index'))
            
            # Validate file extension
            allowed_ext = app.config['ALLOWED_EXTENSIONS']
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_ext:
                flash(f'Invalid file type. Allowed: {", ".join(allowed_ext)}', 'error')
                return redirect(url_for('index'))
            
            # Save and process file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Extract text from resume
            try:
                resume_text = extract_text_from_file(filepath)
            except Exception as e:
                flash(f'Error parsing resume: {str(e)}', 'error')
                return redirect(url_for('index'))
            
            # Get candidate name (optional form field)
            candidate_name = request.form.get('candidate_name', 'Candidate')
            
            # Process through pipeline
            p = get_pipeline()
            results = p.process_resume(resume_text, candidate_name)
            
            # Load learning resources
            try:
                with open(app.config['LEARNING_FILE'], 'r') as f:
                    learning_data = json.load(f)
                    if isinstance(learning_data, dict) and 'learning_resources' in learning_data:
                        learning_resources = learning_data['learning_resources']
                    else:
                        learning_resources = {}
            except Exception as e:
                logger.error(f"Error loading learning resources: {e}")
                learning_resources = {}
            
            # Get learning recommendations
            recommendations = p.get_learning_recommendations(results.get('skill_gaps', []), learning_resources)
            results['learning_recommendations'] = recommendations
            
            # Generate interview questions
            results['interview_questions'] = generate_interview_questions(results.get('extracted_skills', []))
            
            # Save results to session/storage for report page
            # For simplicity, we'll pass data directly (in production, use sessions/database)
            return render_template('report.html', results=results)
            
        except Exception as e:
            logger.error(f"Error in analyze route: {e}", exc_info=True)
            flash(f'Error processing resume: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/api/analyze', methods=['POST'])
    def api_analyze():
        """API endpoint for resume analysis (JSON API)."""
        try:
            # Validate and extract resume
            if 'resume_file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['resume_file']
            
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Save and process file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Extract text
            try:
                resume_text = extract_text_from_file(filepath)
            except Exception as e:
                return jsonify({'error': f'Error parsing resume: {str(e)}'}), 400
            
            # Get candidate name
            candidate_name = request.form.get('candidate_name', 'Candidate')
            
            # Process through pipeline
            p = get_pipeline()
            results = p.process_resume(resume_text, candidate_name)
            
            # Add learning recommendations
            try:
                with open(app.config['LEARNING_FILE'], 'r') as f:
                    learning_data = json.load(f)
                    if isinstance(learning_data, dict) and 'learning_resources' in learning_data:
                        learning_resources = learning_data['learning_resources']
                    else:
                        learning_resources = {}
            except:
                learning_resources = {}
            
            recommendations = p.get_learning_recommendations(results.get('skill_gaps', []), learning_resources)
            results['learning_recommendations'] = recommendations
            results['interview_questions'] = generate_interview_questions(results.get('extracted_skills', []))
            
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Error in API analyze: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/skills')
    def skills():
        """Display available skills by category."""
        try:
            extractor = get_skill_extractor()
            categories = extractor.get_categories()
            skills_by_cat = {}
            
            for category in categories:
                skills_by_cat[category] = extractor.skills_by_category.get(category, [])
            
            return render_template('skills.html', categories=skills_by_cat)
        except Exception as e:
            flash(f'Error loading skills: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/jobs')
    def jobs():
        """Display available job roles."""
        try:
            matcher = get_resume_matcher()
            jobs_list = matcher.jobs_data
            
            return render_template('jobs.html', jobs=jobs_list)
        except Exception as e:
            flash(f'Error loading jobs: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'message': 'AI Hiring Agent is running'
        })
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file too large error."""
        max_size_mb = app.config['MAX_RESUME_FILE_SIZE'] / (1024 * 1024)
        flash(f'File too large. Maximum size: {max_size_mb}MB', 'error')
        return redirect(url_for('index'))
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return render_template('error.html', error='Page not found'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        return render_template('error.html', error='Internal server error'), 500
    
    return app


def generate_interview_questions(skills: list) -> dict:
    """Generate interview questions based on extracted skills."""
    
    # Question banks for different skill categories
    question_bank = {
        'python': [
            'Explain the difference between a list and a tuple in Python.',
            'What are Python decorators and how do you use them?',
            'Explain the GIL (Global Interpreter Lock) in Python.',
            'How do you handle exceptions in Python?',
            'What is the difference between shallow and deep copy?'
        ],
        'machine learning': [
            'Explain the difference between supervised and unsupervised learning.',
            'What is overfitting and how can you prevent it?',
            'Explain the bias-variance tradeoff.',
            'What are the advantages of using gradient descent?',
            'How do you choose the right algorithm for a given problem?'
        ],
        'deep learning': [
            'Explain the backpropagation algorithm.',
            'What is a neural network activation function?',
            'Explain the difference between CNN and RNN.',
            'What is transfer learning and when would you use it?',
            'How do you prevent vanishing gradients?'
        ],
        'tensorflow': [
            'Explain the computational graph in TensorFlow.',
            'What are TensorFlow tensors?',
            'How do you create a custom model in TensorFlow?',
            'Explain the difference between TensorFlow 1.x and 2.x.',
            'What is TensorFlow Serving?'
        ],
        'pytorch': [
            'Explain the difference between torch.tensor and torch.nn.Parameter.',
            'What are the advantages of PyTorch over TensorFlow?',
            'How do you create a custom dataset in PyTorch?',
            'Explain the use of DataLoader in PyTorch.',
            'What is torch.autograd?'
        ],
        'docker': [
            'Explain the difference between a Docker image and container.',
            'What is a Dockerfile and how do you use it?',
            'How do you manage data in Docker volumes?',
            'Explain Docker networking.',
            'What is Docker Compose?'
        ],
        'kubernetes': [
            'Explain the architecture of Kubernetes.',
            'What is a Pod in Kubernetes?',
            'How do you manage secrets in Kubernetes?',
            'Explain Kubernetes services and ingress.',
            'What is a Deployment and how does it work?'
        ],
        'aws': [
            'Explain the different AWS storage services.',
            'What is EC2 and how does it work?',
            'Explain AWS Lambda and when to use it.',
            'What is AWS VPC?',
            'How do you secure AWS resources?'
        ],
        'sql': [
            'Explain the difference between INNER JOIN and LEFT JOIN.',
            'What are indexes and how do they improve performance?',
            'Explain database normalization.',
            'What is a subquery?',
            'How do you optimize slow SQL queries?'
        ],
        'django': [
            'Explain the MVT architecture in Django.',
            'What are Django models and migrations?',
            'How do you handle authentication in Django?',
            'Explain Django middleware.',
            'What are Django signals?'
        ],
        'react': [
            'Explain the difference between props and state in React.',
            'What is the virtual DOM?',
            'Explain React hooks and their use cases.',
            'What is Redux and when would you use it?',
            'How do you handle forms in React?'
        ],
        'javascript': [
            'Explain closures in JavaScript.',
            'What is the difference between var, let, and const?',
            'Explain the event loop in JavaScript.',
            'What are JavaScript promises?',
            'How do you handle asynchronous operations?'
        ],
        'data analysis': [
            'Explain the data analysis pipeline.',
            'What is exploratory data analysis?',
            'How do you handle missing data?',
            'What are the key steps in data cleaning?',
            'Explain the difference between correlation and causation.'
        ],
        'nlp': [
            'Explain the difference between NLP and NLU.',
            'What is tokenization in NLP?',
            'Explain the transformer architecture.',
            'What is BERT and how does it work?',
            'How do you handle text classification?'
        ],
        'computer vision': [
            'Explain the CNN architecture.',
            'What is object detection?',
            'Explain YOLO and its working.',
            'What is image segmentation?',
            'How do you handle image preprocessing?'
        ]
    }
    
    questions = {}
    skills_lower = [s.lower() for s in skills]
    
    for skill in skills_lower:
        # Check for exact match
        if skill in question_bank:
            questions[skill] = question_bank[skill][:3]
        else:
            # Check for partial match
            for key in question_bank:
                if key in skill or skill in key:
                    questions[key] = question_bank[key][:3]
                    break
    
    return questions


# Create the Flask application
app = create_app(os.environ.get('FLASK_ENV', 'default'))


if __name__ == '__main__':
    # Run the Flask application
    app.run(
        debug=app.config['DEBUG'],
        host='0.0.0.0',
        port=5000
    )

