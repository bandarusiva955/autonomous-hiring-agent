"""
Hiring Scorer - Calculate hiring scores and make decisions.
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class HiringScorer:
    """Calculate hiring scores and classify candidates."""
    
    def __init__(self, strong_threshold: float = 0.75, 
                 consider_threshold: float = 0.45):
        """
        Initialize the hiring scorer.
        
        Args:
            strong_threshold: Threshold for "Strong Hire"
            consider_threshold: Threshold for "Consider"
        """
        self.strong_threshold = strong_threshold
        self.consider_threshold = consider_threshold
        
        # Scoring weights
        self.weights = {
            'skill_match': 0.35,
            'skill_count': 0.15,
            'technical_ratio': 0.20,
            'critical_skills': 0.30
        }
    
    def calculate_score(self, resume_skills: List[str], job_match: Dict) -> Dict:
        """
        Calculate overall hiring score.
        
        Args:
            resume_skills: List of candidate's skills
            job_match: Job match results from ResumeMatcher
            
        Returns:
            Dictionary with score breakdown and decision
        """
        # Component 1: Skill match percentage (0-1)
        skill_match = job_match.get('match_percentage', 0) / 100.0
        
        # Component 2: Skill count ratio (normalize to 0-1)
        # Assume 10+ skills is optimal
        skill_count = min(len(resume_skills) / 10.0, 1.0)
        
        # Component 3: Technical skills ratio
        # Count technical vs total skills
        technical_keywords = ['python', 'java', 'javascript', 'c++', 'sql', 'machine learning',
                           'docker', 'aws', 'react', 'django', 'flask', 'tensorflow']
        tech_skills = [s for s in resume_skills if s.lower() in technical_keywords]
        technical_ratio = len(tech_skills) / max(len(resume_skills), 1)
        
        # Component 4: Critical skills match
        # Check if core job skills are present
        matched_skills = job_match.get('matched_skills', [])
        critical_skills = matched_skills  # Use matched skills as proxy
        critical_skills_ratio = len(critical_skills) / max(len(job_match.get('matched_skills', [])), 1)
        
        # Calculate weighted score
        weighted_score = (
            skill_match * self.weights['skill_match'] +
            skill_count * self.weights['skill_count'] +
            technical_ratio * self.weights['technical_ratio'] +
            critical_skills_ratio * self.weights['critical_skills']
        )
        
        # Also factor in similarity score
        similarity = job_match.get('similarity_score', 0)
        
        # Final score is combination of weighted components and similarity
        final_score = (weighted_score * 0.6 + similarity * 0.4)
        
        # Make decision
        decision = self.make_decision(final_score)
        
        return {
            'final_score': round(final_score, 4),
            'skill_match_score': round(skill_match, 4),
            'skill_count_score': round(skill_count, 4),
            'technical_ratio_score': round(technical_ratio, 4),
            'critical_skills_score': round(critical_skills_ratio, 4),
            'similarity_score': round(similarity, 4),
            'decision': decision,
            'matched_skills_count': len(matched_skills),
            'missing_skills_count': len(job_match.get('missing_skills', []))
        }
    
    def make_decision(self, score: float) -> str:
        """
        Make hiring decision based on score.
        
        Args:
            score: Calculated score
            
        Returns:
            Decision string: "Strong Hire", "Consider", or "Reject"
        """
        if score >= self.strong_threshold:
            return "Strong Hire"
        elif score >= self.consider_threshold:
            return "Consider"
        else:
            return "Reject"
    
    def score_candidate(self, resume_skills: List[str], job_matches: List[Dict]) -> Dict:
        """
        Score a candidate against multiple jobs.
        
        Args:
            resume_skills: List of candidate's skills
            job_matches: List of job matches
            
        Returns:
            Complete scoring results
        """
        if not job_matches:
            return {
                'overall_score': 0,
                'decision': 'No Jobs Available',
                'best_role': 'N/A',
                'job_scores': []
            }
        
        # Score against each job
        job_scores = []
        for job_match in job_matches:
            score_result = self.calculate_score(resume_skills, job_match)
            job_scores.append({
                'role': job_match.get('role'),
                'score': score_result['final_score'],
                'decision': score_result['decision'],
                'similarity': job_match.get('similarity_score'),
                'match_percentage': job_match.get('match_percentage')
            })
        
        # Find best job
        best_job = max(job_scores, key=lambda x: x['score'])
        
        return {
            'overall_score': best_job['score'],
            'decision': best_job['decision'],
            'best_role': best_job['role'],
            'job_scores': job_scores
        }


def calculate_hiring_score(resume_skills: List[str], job_match: Dict) -> Dict:
    """
    Standalone function to calculate hiring score.
    
    Args:
        resume_skills: Candidate skills
        job_match: Job match result
        
    Returns:
        Score results
    """
    scorer = HiringScorer()
    return scorer.calculate_score(resume_skills, job_match)


if __name__ == "__main__":
    # Test the scorer
    scorer = HiringScorer()
    
    test_skills = ['python', 'machine learning', 'django', 'flask', 'sql', 'docker']
    
    test_job_match = {
        'role': 'Data Scientist',
        'similarity_score': 0.82,
        'match_percentage': 75.0,
        'matched_skills': ['python', 'machine learning', 'sql'],
        'missing_skills': ['tensorflow', 'pytorch', 'statistics']
    }
    
    result = scorer.calculate_score(test_skills, test_job_match)
    
    print("Hiring Score Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")
