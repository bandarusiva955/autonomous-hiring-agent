"""Tests for the resume processing pipeline."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import ResumeProcessingPipeline  # noqa: E402

ML_RESUME = """
Machine learning engineer with experience in Python, SQL, pandas, numpy,
scikit-learn and TensorFlow. Built classification models and data analysis
dashboards. Deployed services with Docker on AWS.
"""


def test_extracts_skills():
    results = ResumeProcessingPipeline().process_resume(ML_RESUME, "Test")
    skills = set(results["extracted_skills"])
    assert {"python", "sql"} <= skills


def test_returns_best_match_and_decision():
    results = ResumeProcessingPipeline().process_resume(ML_RESUME, "Test")
    assert results["best_match"] is not None
    assert results["hiring_score"]["decision"] in {"Strong Hire", "Consider", "Reject"}
    assert 0 <= results["hiring_score"]["overall_score"] <= 1


def test_skill_gaps_are_deterministic():
    """Missing skills must come back in the same order on every run."""
    pipeline = ResumeProcessingPipeline()
    first = pipeline.process_resume(ML_RESUME, "Test")["skill_gaps"]
    second = pipeline.process_resume(ML_RESUME, "Test")["skill_gaps"]
    assert first == second


def test_core_skill_gaps_listed_first_and_marked_high():
    results = ResumeProcessingPipeline().process_resume(ML_RESUME, "Test")
    best = results["best_match"]
    core = set(best["core_skills"])
    gaps = results["skill_gaps"]
    for gap in gaps:
        assert gap["importance"] == ("high" if gap["skill"] in core else "medium")
    # once a non-core gap appears, no core gap may follow it
    seen_non_core = False
    for gap in gaps:
        if gap["skill"] not in core:
            seen_non_core = True
        else:
            assert not seen_non_core


def test_empty_resume_does_not_crash():
    results = ResumeProcessingPipeline().process_resume("", "Nobody")
    assert results["candidate_name"] == "Nobody"
    assert results["extracted_skills"] == []
