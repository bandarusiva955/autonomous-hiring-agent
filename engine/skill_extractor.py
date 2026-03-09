"""
Skill Extractor - Extract skills from resumes using comprehensive skills database.
"""
import json
import re
import logging
from typing import List, Dict, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillExtractor:
    """Extract skills from resume text using comprehensive skills database."""
    
    def __init__(self, skills_file: str = None):
        """
        Initialize the skill extractor.
        
        Args:
            skills_file: Path to skills JSON file
        """
        if skills_file is None:
            base_dir = Path(__file__).parent.parent
            skills_file = base_dir / "data" / "skills_master.json"
        
        self.skills_file = skills_file
        self.skills_data = []
        self.skills_by_category = {}
        self.skill_weights = {}
        self._load_skills()
        
    def _load_skills(self):
        """Load skills from the database file."""
        try:
            with open(self.skills_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'skills' in data:
                self.skills_data = data['skills']
            elif isinstance(data, list):
                self.skills_data = data
            else:
                self.skills_data = []
            
            # Build skills by category
            for skill_entry in self.skills_data:
                skill = skill_entry.get('skill', '').lower()
                category = skill_entry.get('category', 'unknown')
                weight = skill_entry.get('weight', 1.0)
                
                if skill:
                    if category not in self.skills_by_category:
                        self.skills_by_category[category] = []
                    self.skills_by_category[category].append(skill)
                    self.skill_weights[skill] = weight
            
            logger.info(f"Loaded {len(self.skills_data)} skills in {len(self.skills_by_category)} categories")
            
        except FileNotFoundError:
            logger.error(f"Skills file not found: {self.skills_file}")
            self.skills_data = []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing skills JSON: {e}")
            self.skills_data = []
    
    def extract_skills(self, text: str) -> List[Dict]:
        """
        Extract skills from resume text.
        
        Args:
            text: Resume text content
            
        Returns:
            List of extracted skills with metadata
        """
        text_lower = text.lower()
        found_skills = []
        seen_skills = set()
        
        # Sort skills by length (longest first) to match more specific skills first
        sorted_skills = sorted(
            self.skills_data, 
            key=lambda x: len(x.get('skill', '')), 
            reverse=True
        )
        
        for skill_entry in sorted_skills:
            skill = skill_entry.get('skill', '').lower()
            
            if skill in seen_skills:
                continue
            
            # Create pattern to match whole word/phrase
            pattern = r'\b' + re.escape(skill) + r'\b'
            
            if re.search(pattern, text_lower):
                found_skills.append({
                    'skill': skill_entry.get('skill'),
                    'category': skill_entry.get('category', 'unknown'),
                    'weight': skill_entry.get('weight', 1.0)
                })
                seen_skills.add(skill)
        
        logger.info(f"Extracted {len(found_skills)} unique skills from text")
        return found_skills
    
    def extract_skills_by_category(self, text: str) -> Dict[str, List[str]]:
        """
        Extract skills grouped by category.
        
        Args:
            text: Resume text content
            
        Returns:
            Dictionary of category -> skills list
        """
        skills = self.extract_skills(text)
        
        by_category = {}
        for skill_entry in skills:
            category = skill_entry['category']
            skill = skill_entry['skill']
            
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(skill)
        
        return by_category
    
    def get_skill_weight(self, skill: str) -> float:
        """
        Get weight for a specific skill.
        
        Args:
            skill: Skill name
            
        Returns:
            Skill weight (default 1.0)
        """
        return self.skill_weights.get(skill.lower(), 1.0)
    
    def get_categories(self) -> List[str]:
        """
        Get all available skill categories.
        
        Returns:
            List of category names
        """
        return list(self.skills_by_category.keys())


def extract_skills_from_resume(text: str, skills_file: str = None) -> List[Dict]:
    """
    Standalone function to extract skills from resume text.
    
    Args:
        text: Resume text
        skills_file: Path to skills database
        
    Returns:
        List of extracted skills
    """
    extractor = SkillExtractor(skills_file)
    return extractor.extract_skills(text)


if __name__ == "__main__":
    # Test the skill extractor
    print("Testing Skill Extractor...")
    
    extractor = SkillExtractor()
    
    test_resume = """
    JOHN DOE
    Software Engineer
    
    Experience:
    - 5 years of experience in Python and Java development
    - Proficient in Django, Flask, React, and Docker
    - Experience with AWS cloud services and PostgreSQL database
    - Machine learning and data analysis using TensorFlow and scikit-learn
    - Worked with Kubernetes and Terraform for DevOps
    - Strong in SQL, Git, and Linux
    - Experience with REST APIs and GraphQL
    """
    
    skills = extractor.extract_skills(test_resume)
    
    print(f"\nExtracted {len(skills)} skills:")
    for skill in skills[:20]:
        print(f"  - {skill['skill']} ({skill['category']})")
    
    # Show categories
    by_category = extractor.extract_skills_by_category(test_resume)
    print(f"\nSkills by category:")
    for category, cat_skills in by_category.items():
        print(f"  {category}: {cat_skills}")

