"""
Pipeline - Main orchestration for the AI Hiring Agent.
"""
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .skill_extractor import SkillExtractor
from .resume_matcher import ResumeMatcher
from .hiring_scorer import HiringScorer
from .graph_builder import GraphBuilder

logger = logging.getLogger(__name__)

class ResumeProcessingPipeline:
    """Main pipeline for processing resumes and generating hiring recommendations."""
    
    def __init__(self, skills_file: str = None, jobs_file: str = None):
        """
        Initialize the processing pipeline.
        
        Args:
            skills_file: Path to skills database
            jobs_file: Path to jobs database
        """
        # Initialize components
        self.skill_extractor = SkillExtractor(skills_file)
        self.resume_matcher = ResumeMatcher(jobs_file)
        self.hiring_scorer = HiringScorer()
        self.graph_builder = GraphBuilder(jobs_file)
        
        logger.info("Pipeline initialized successfully")
    
    def process_resume(self, resume_text: str, candidate_name: str = "Candidate") -> Dict:
        """
        Process a resume through the complete pipeline.
        
        Args:
            resume_text: The resume text content
            candidate_name: Name of the candidate
            
        Returns:
            Complete analysis results
        """
        logger.info(f"Processing resume for: {candidate_name}")
        
        # Step 1: Extract skills
        logger.info("Step 1: Extracting skills...")
        extracted_skills = self.skill_extractor.extract_skills(resume_text)
        skill_names = [s['skill'] for s in extracted_skills]
        
        logger.info(f"Found {len(skill_names)} skills")
        
        # Step 2: Match against jobs
        logger.info("Step 2: Matching against jobs...")
        job_matches = self.resume_matcher.match_resume(resume_text, skill_names)
        
        logger.info(f"Matched against {len(job_matches)} jobs")
        
        # Step 3: Calculate hiring scores
        logger.info("Step 3: Calculating hiring scores...")
        if job_matches:
            scoring_result = self.hiring_scorer.score_candidate(skill_names, job_matches)
            
            # Add detailed score breakdown for the template
            # Get detailed scores from the best job match
            if job_matches and scoring_result.get('job_scores'):
                best_job_score = scoring_result['job_scores'][0]
                # Calculate detailed breakdown using the best match
                detailed_scores = self.hiring_scorer.calculate_score(skill_names, job_matches[0])
                scoring_result.update({
                    'skill_match_score': detailed_scores.get('skill_match_score', 0),
                    'skill_count_score': detailed_scores.get('skill_count_score', 0),
                    'technical_ratio_score': detailed_scores.get('technical_ratio_score', 0),
                    'critical_skills_score': detailed_scores.get('critical_skills_score', 0),
                    'similarity_score': detailed_scores.get('similarity_score', 0),
                    'matched_skills_count': detailed_scores.get('matched_skills_count', 0),
                    'missing_skills_count': detailed_scores.get('missing_skills_count', 0)
                })
        else:
            scoring_result = {
                'overall_score': 0,
                'decision': 'No Jobs Available',
                'best_role': 'N/A',
                'job_scores': [],
                'skill_match_score': 0,
                'skill_count_score': 0,
                'technical_ratio_score': 0,
                'critical_skills_score': 0,
                'similarity_score': 0,
                'matched_skills_count': 0,
                'missing_skills_count': 0
            }
        
        # Step 4: Build graph
        logger.info("Step 4: Building candidate-job graph...")
        graph = self.graph_builder.build_candidate_graph(
            candidate_name, 
            job_matches,
            similarity_threshold=0.3
        )
        graph_data = self.graph_builder.get_graph_data(graph)
        
        # Compile results
        results = {
            'candidate_name': candidate_name,
            'extracted_skills': skill_names,
            'skills_by_category': self._group_skills_by_category(extracted_skills),
            'job_matches': job_matches[:10],  # Top 10 matches
            'best_match': job_matches[0] if job_matches else None,
            'hiring_score': scoring_result,
            'graph_data': graph_data,
            'skill_gaps': self._get_skill_gaps(job_matches, skill_names) if job_matches else []
        }
        
        logger.info(f"Processing complete. Decision: {scoring_result.get('decision', 'Unknown')}")
        
        return results
    
    def _group_skills_by_category(self, skills: List[Dict]) -> Dict[str, List[str]]:
        """Group extracted skills by category."""
        categories = {}
        for skill in skills:
            cat = skill.get('category', 'unknown')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(skill['skill'])
        return categories
    
    def _get_skill_gaps(self, job_matches: List[Dict], 
                       candidate_skills: List[str]) -> List[Dict]:
        """Identify skill gaps for the best matching job."""
        if not job_matches:
            return []
        
        best_match = job_matches[0]
        missing = best_match.get('missing_skills', [])
        
        skill_gaps = []
        for skill in missing[:5]:  # Top 5 missing skills
            skill_gaps.append({
                'skill': skill,
                'importance': 'high' if skill in best_match.get('matched_skills', []) else 'medium'
            })
        
        return skill_gaps
    
    def get_learning_recommendations(self, skill_gaps: List[Dict],
                                    learning_resources: Dict = None) -> List[Dict]:
        """
        Get learning resource recommendations for skill gaps.
        
        Args:
            skill_gaps: List of missing skills
            learning_resources: Learning resources database
            
        Returns:
            List of recommended resources
        """
        if learning_resources is None:
            # Try to load from file
            try:
                base_dir = Path(__file__).parent.parent
                resources_file = base_dir / "data" / "learning_resources.json"
                import json
                with open(resources_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'resources' in data:
                        learning_resources = data['resources']
                    else:
                        learning_resources = []
            except Exception as e:
                logger.error(f"Error loading learning resources: {e}")
                learning_resources = []
        
        recommendations = []
        
        for gap in skill_gaps:
            skill = gap.get('skill', '').lower()
            
            # Find resources for this skill
            for resource_entry in learning_resources:
                if resource_entry.get('skill', '').lower() == skill:
                    recommendations.append({
                        'skill': skill,
                        'resources': resource_entry.get('resources', [])
                    })
                    break
        
        return recommendations


def process_resume_pipeline(resume_text: str, candidate_name: str = "Candidate",
                           skills_file: str = None, jobs_file: str = None) -> Dict:
    """
    Standalone function to process a resume through the pipeline.
    
    Args:
        resume_text: Resume content
        candidate_name: Candidate name
        skills_file: Skills database path
        jobs_file: Jobs database path
        
    Returns:
        Complete analysis results
    """
    pipeline = ResumeProcessingPipeline(skills_file, jobs_file)
    return pipeline.process_resume(resume_text, candidate_name)


if __name__ == "__main__":
    # Test the pipeline
    print("Testing Resume Processing Pipeline...")
    
    test_resume = """
    JOHN DOE
    
    Software Engineer with 5 years of experience in Python, Java, and JavaScript.
    Proficient in Django, Flask, React, and Docker.
    Experienced with AWS cloud services and SQL databases.
    Machine learning and data analysis skills.
    Worked with TensorFlow and scikit-learn.
    """
    
    pipeline = ResumeProcessingPipeline()
    results = pipeline.process_resume(test_resume, "John Doe")
    
    print("\n=== PROCESSING RESULTS ===")
    print(f"Candidate: {results['candidate_name']}")
    print(f"\nExtracted Skills ({len(results['extracted_skills'])}):")
    for skill in results['extracted_skills'][:10]:
        print(f"  - {skill}")
    
    print(f"\nBest Match: {results['best_match']['role'] if results['best_match'] else 'None'}")
    print(f"Match Score: {results['best_match']['similarity_score'] if results['best_match'] else 0}")
    
    print(f"\nHiring Decision: {results['hiring_score']['decision']}")
    print(f"Overall Score: {results['hiring_score']['overall_score']}")
    
    print(f"\nSkill Gaps:")
    for gap in results['skill_gaps']:
        print(f"  - {gap['skill']} ({gap['importance']})")
