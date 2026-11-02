"""
Roadmaps - career learning paths that can be personalized with a skill list.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class RoadmapLibrary:
    """Loads roadmaps from JSON and personalizes them against known skills."""

    def __init__(self, roadmaps_file: str = None):
        if roadmaps_file is None:
            roadmaps_file = Path(__file__).parent.parent / "data" / "roadmaps.json"
        self.roadmaps_file = roadmaps_file
        self.roadmaps: List[Dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.roadmaps_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.roadmaps = data.get('roadmaps', []) if isinstance(data, dict) else []
            logger.info(f"Loaded {len(self.roadmaps)} roadmaps")
        except (OSError, ValueError) as e:
            logger.error(f"Could not load roadmaps: {e}")
            self.roadmaps = []

    def all(self) -> List[Dict]:
        return self.roadmaps

    def get(self, slug: str) -> Optional[Dict]:
        for roadmap in self.roadmaps:
            if roadmap.get('slug') == slug:
                return roadmap
        return None

    def recommend_for_role(self, role: str) -> Optional[Dict]:
        """Return the roadmap whose `roles` list contains the given role."""
        if not role:
            return None
        role_lower = role.lower()
        for roadmap in self.roadmaps:
            if role_lower in (r.lower() for r in roadmap.get('roles', [])):
                return roadmap
        return None

    def recommend_for_gaps(self, missing_skills: Iterable[str]) -> Optional[Dict]:
        """Return the roadmap that covers the most of the given missing skills."""
        missing = {s.lower() for s in missing_skills if s}
        best, best_count = None, 0
        for roadmap in self.roadmaps:
            tags = {t.lower() for stage in roadmap.get('stages', []) for t in stage.get('skills', [])}
            count = len(tags & missing)
            if count > best_count:
                best, best_count = roadmap, count
        return best

    def personalize(self, roadmap: Dict, known_skills: Iterable[str]) -> Dict:
        """
        Mark each stage with the skills the person already has and the ones
        still missing, plus an overall progress percentage.

        Stage status: done (all skills known), in_progress (some), todo (none).
        """
        known = {s.strip().lower() for s in known_skills if s and s.strip()}
        stages = []
        total_tags = 0
        known_tags = 0
        next_stage = None

        for stage in roadmap.get('stages', []):
            tags = [t.lower() for t in stage.get('skills', [])]
            have = [t for t in tags if t in known]
            missing = [t for t in tags if t not in known]
            total_tags += len(tags)
            known_tags += len(have)

            if tags and not missing:
                status = 'done'
            elif have:
                status = 'in_progress'
            else:
                status = 'todo'

            enriched = dict(stage)
            enriched.update({'have': have, 'missing': missing, 'status': status})
            stages.append(enriched)

            if next_stage is None and status != 'done':
                next_stage = stage.get('title')

        progress = round(100 * known_tags / total_tags) if total_tags else 0
        result = dict(roadmap)
        result.update({
            'stages': stages,
            'progress': progress,
            'next_stage': next_stage,
            'skills_known': known_tags,
            'skills_total': total_tags,
        })
        return result
