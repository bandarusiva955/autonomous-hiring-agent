"""
Resume Matcher - TF-IDF and Cosine Similarity matching.
"""
import json
import logging
from typing import List, Dict, Tuple
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class ResumeMatcher:
    """Match resumes to job descriptions using TF-IDF and cosine similarity."""
    
    def __init__(self, jobs_file: str = None, max_features: int = 5000):
        """
        Initialize the resume matcher.
        
        Args:
            jobs_file: Path to jobs JSON file
            max_features: Maximum TF-IDF features
        """
        if jobs_file is None:
            base_dir = Path(__file__).parent.parent
            jobs_file = base_dir / "data" / "jobs.json"
        
        self.jobs_file = jobs_file
        self.jobs_data = []
        self.vectorizer = None
        self.job_vectors = None
        self._load_jobs()
        
        self.max_features = max_features
        
    def _load_jobs(self):
        """Load jobs from the database file."""
        try:
            with open(self.jobs_file, 'r') as f:
                self.jobs_data = json.load(f)
            
            if isinstance(self.jobs_data, dict):
                self.jobs_data = self.jobs_data.get('jobs', [])
            elif not isinstance(self.jobs_data, list):
                self.jobs_data = []
            
            logger.info(f"Loaded {len(self.jobs_data)} job profiles")
            
        except FileNotFoundError:
            logger.error(f"Jobs file not found: {self.jobs_file}")
            self.jobs_data = []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing jobs JSON: {e}")
            self.jobs_data = []
    
    def _create_job_text(self, job: Dict) -> str:
        """Create text representation of a job for TF-IDF."""
        text_parts = []
        
        # Add role name
        text_parts.append(job.get('role', ''))
        
        # Add description
        text_parts.append(job.get('description', ''))
        
        # Add core skills
        core_skills = job.get('core_skills', [])
        if core_skills:
            text_parts.extend(core_skills)
        
        # Add secondary skills
        secondary_skills = job.get('secondary_skills', [])
        if secondary_skills:
            text_parts.extend(secondary_skills)
        
        # Add experience level
        text_parts.append(job.get('experience_level', ''))
        
        return ' '.join(text_parts)
    
    def _fit_vectorizer(self):
        """Fit TF-IDF vectorizer on all job descriptions."""
        job_texts = [self._create_job_text(job) for job in self.jobs_data]
        
        if not job_texts:
            logger.warning("No job texts to fit vectorizer")
            return
        
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=(1, 2),  # Use unigrams and bigrams
            stop_words='english',
            lowercase=True
        )
        
        self.job_vectors = self.vectorizer.fit_transform(job_texts)
        logger.info(f"Fitted TF-IDF vectorizer with {self.job_vectors.shape[1]} features")
    
    def match_resume(self, resume_text: str, resume_skills: List[str] = None) -> List[Dict]:
        """
        Match a resume against all jobs.
        
        Args:
            resume_text: Full resume text
            resume_skills: Optional list of extracted skills
            
        Returns:
            List of job match results sorted by score
        """
        # Refit vectorizer if needed
        if self.vectorizer is None or self.job_vectors is None:
            self._fit_vectorizer()
        
        if not self.jobs_data or self.job_vectors is None:
            logger.warning("No jobs available for matching")
            return []
        
        # Create resume text (use skills if provided for better matching)
        if resume_skills:
            resume_text_for_matching = ' '.join(resume_skills) + ' ' + resume_text[:1000]
        else:
            resume_text_for_matching = resume_text[:2000]
        
        # Transform resume using the fitted vectorizer
        resume_vector = self.vectorizer.transform([resume_text_for_matching])
        
        # Calculate cosine similarity
        similarities = cosine_similarity(resume_vector, self.job_vectors)[0]
        
        # Build results
        results = []
        for idx, job in enumerate(self.jobs_data):
            score = float(similarities[idx])
            
            # Calculate skill match
            job_core_skills = set(job.get('core_skills', []))
            job_secondary_skills = set(job.get('secondary_skills', []))
            job_all_skills = job_core_skills | job_secondary_skills
            
            matched_skills = []
            missing_skills = []
            
            if resume_skills:
                resume_skills_set = set(s.lower() for s in resume_skills)
                matched = job_all_skills & resume_skills_set
                missing = job_all_skills - resume_skills_set
                matched_skills = list(matched)
                missing_skills = list(missing)
            
            # Calculate match percentage
            if job_all_skills:
                match_percentage = len(matched_skills) / len(job_all_skills)
            else:
                match_percentage = 0
            
            result = {
                'role': job.get('role'),
                'similarity_score': round(score, 4),
                'match_percentage': round(match_percentage * 100, 2),
                'matched_skills': matched_skills,
                'missing_skills': missing_skills,
                'experience_level': job.get('experience_level'),
                'description': job.get('description')
            }
            results.append(result)
        
        # Sort by similarity score
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return results
    
    def get_best_match(self, resume_text: str, resume_skills: List[str] = None) -> Dict:
        """
        Get the best matching job for a resume.
        
        Args:
            resume_text: Full resume text
            resume_skills: Optional list of extracted skills
            
        Returns:
            Best job match dictionary
        """
        matches = self.match_resume(resume_text, resume_skills)
        
        if matches:
            return matches[0]
        
        return {
            'role': 'No match found',
            'similarity_score': 0,
            'match_percentage': 0,
            'matched_skills': [],
            'missing_skills': []
        }


def match_resume_to_jobs(resume_text: str, jobs_file: str = None, 
                         resume_skills: List[str] = None) -> List[Dict]:
    """
    Standalone function to match resume to jobs.
    
    Args:
        resume_text: Resume text
        jobs_file: Path to jobs JSON
        resume_skills: Extracted skills
        
    Returns:
        List of job matches
    """
    matcher = ResumeMatcher(jobs_file)
    return matcher.match_resume(resume_text, resume_skills)


if __name__ == "__main__":
    # Test the matcher
    matcher = ResumeMatcher()
    
    test_resume = """
    Python developer with experience in machine learning and data analysis.
    Proficient in Django, Flask, SQL, and Docker.
    Worked with AWS and React.
    """
    
    test_skills = ['python', 'machine learning', 'django', 'flask', 'sql', 'docker', 'aws', 'react']
    
    matches = matcher.match_resume(test_resume, test_skills)
    
    print("Job Matches:")
    for match in matches[:5]:
        print(f"\n{match['role']}")
        print(f"  Similarity: {match['similarity_score']:.4f}")
        print(f"  Match %: {match['match_percentage']:.1f}%")
        print(f"  Matched: {match['matched_skills']}")
        print(f"  Missing: {match['missing_skills']}")
