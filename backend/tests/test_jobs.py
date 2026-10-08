"""Deterministic job scoring must be stable."""

from backend.models import Profile, SeedJob
from backend.services import jobs as jobs_svc
from backend.services.jobs import deterministic_skill_score


def _profile() -> Profile:
    return Profile(
        name="Olena",
        summary="Hospital nurse providing patient care, vital signs, wound care, infection control.",
        skills=["patient care", "vital signs", "teamwork", "empathy", "record keeping", "infection control"],
        experience=[],
    )


def _job() -> SeedJob:
    return SeedJob(
        id="t1",
        title="Healthcare Assistant",
        employer="NHS",
        location="Manchester",
        salary="£24k",
        description="Support nurses",
        required_skills=["patient care", "vital signs", "teamwork", "record keeping", "empathy", "infection control"],
        nice_to_have=["NHS experience", "Care Certificate"],
    )


def test_score_is_deterministic():
    p, j = _profile(), _job()
    a = deterministic_skill_score(p, j)
    b = deterministic_skill_score(p, j)
    assert a == b
    assert a["score"] >= 70
    assert a["verdict"] == "relevant"


def test_unrelated_job_is_not_relevant():
    p = _profile()
    j = SeedJob(
        id="it",
        title="IT Support",
        employer="Co",
        location="Manchester",
        salary="",
        description="",
        required_skills=["Active Directory", "CompTIA", "Python", "networking"],
        nice_to_have=["AWS"],
    )
    s = deterministic_skill_score(p, j)
    assert s["verdict"] == "not_relevant"
    assert s["score"] < 40


def test_job_suggestions_are_generated_from_profile(monkeypatch):
    seen = {}

    def fake_complete_json(system, user, schema, *, temperature):
        seen["system"] = system
        seen["user"] = user
        seen["schema"] = schema
        return jobs_svc._GeneratedJobs(
            jobs=[
                jobs_svc._GeneratedJob(
                    title="Healthcare Assistant",
                    description="Support patients and registered staff.",
                    required_skills=["patient care"],
                )
            ]
        )

    monkeypatch.setattr(jobs_svc.llm, "complete_json", fake_complete_json)
    profile = Profile.model_validate(
        {**_profile().model_dump(), "languages": [{"language": "English", "level": "B1"}]}
    )

    suggestions = jobs_svc.generate_job_suggestions(profile, "Healthcare Assistant")

    assert len(suggestions) == 1
    assert suggestions[0].title == "Healthcare Assistant"
    assert suggestions[0].sector == "ai-generated"
    assert suggestions[0].employer == ""
    assert suggestions[0].location == "United Kingdom"
    assert "Not specified" in suggestions[0].salary
    assert "Healthcare Assistant" in seen["user"]
    assert "English" in seen["user"]
    assert seen["schema"] is jobs_svc._GeneratedJobs


def test_job_generation_does_not_invent_jobs_when_llm_unavailable(monkeypatch):
    def fake_fail(*args, **kwargs):
        raise jobs_svc.llm.LlmError("LLM unavailable")

    monkeypatch.setattr(jobs_svc.llm, "complete_json", fake_fail)
    tech_profile = Profile(
        name="Alex",
        summary="Python backend developer with FastAPI and React experience.",
        skills=["Python", "FastAPI", "React", "PostgreSQL"],
        experience=[],
        location="Manchester, UK",
    )

    try:
        jobs_svc.generate_job_suggestions(tech_profile, "Software Developer")
    except jobs_svc.llm.LlmError as exc:
        assert "LLM unavailable" in str(exc)
    else:
        raise AssertionError("Job generation should report LLM failures, not invent jobs")


def test_software_dev_fallback_career_paths(monkeypatch):
    from backend.services import careers as careers_svc

    def fake_fail(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(careers_svc.llm, "complete_json", fake_fail)
    dev_profile = Profile(
        name="Sam",
        summary="Software Engineer specializing in Python and Node.js",
        skills=["Python", "Node.js", "Docker"],
        experience=[],
    )

    res = careers_svc.suggest_paths(dev_profile)
    titles = [p.title for p in res.paths]
    assert any("Software Engineer" in t or "Python" in t for t in titles)
    assert not any("Healthcare" in t or "Nurse" in t or "Teaching" in t for t in titles)

