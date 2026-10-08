"""Tests for analytics insights and language test services."""

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.insights import build_insights
from backend.services.language_test import evaluate_language_sample


def test_insights_post_route_is_registered_and_works():
    response = TestClient(app).post(
        "/api/insights",
        json={
            "jobs": [
                {
                    "role": "Frontend Developer",
                    "co": "WebStudio",
                    "s": "interview",
                    "cat": "Engineering",
                    "type": "Remote",
                    "skills": ["react", "javascript"],
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["stats"]["interview"] == 1


def test_build_insights_rules():
    sample_jobs = [
        {"id": 1, "role": "Software Developer", "co": "TechCorp", "s": "applied", "cat": "Engineering", "type": "Remote", "skills": ["python", "fastapi"]},
        {"id": 2, "role": "Frontend Developer", "co": "WebStudio", "s": "interview", "cat": "Engineering", "type": "Remote", "skills": ["react", "javascript"]},
        {"id": 3, "role": "UI Designer", "co": "DesignCo", "s": "rejected", "cat": "Design", "type": "On-site", "skills": ["figma"]},
    ]
    out = build_insights(sample_jobs)
    assert out["stats"]["total"] == 3
    assert out["stats"]["interview"] == 1
    assert out["stats"]["rejected"] == 1
    assert out["headline"]["tone"] in {"good", "info", "warn"}
    assert len(out["cv"]) > 0
    assert len(out["patterns"]["category"]) > 0


def test_language_test_evaluation(monkeypatch):
    res = evaluate_language_sample("I am a backend developer in London with 4 years experience building API services in Python.")
    assert "CEFR" in res.cefr_level or "Intermediate" in res.cefr_level or "Advanced" in res.cefr_level
    assert res.score >= 50
    assert len(res.clarity_feedback) > 0
