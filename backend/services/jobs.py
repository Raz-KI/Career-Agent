"""Job loading, deterministic scoring, and LLM match judgement."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

from backend import llm, prompts
from backend.config import get_settings
from backend.models import (
    AnalyzeJdRequest,
    GapItem,
    JobMatch,
    Profile,
    SeedJob,
    SkillEvidence,
)

logger = logging.getLogger("pathway.jobs")


class _LlmMatch(BaseModel):
    relevancy_score: int = 0
    verdict: str = "partially_relevant"
    matched_skills: list[SkillEvidence] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    reasoning: str = ""
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    keywords_for_ATS: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class _GeneratedJob(BaseModel):
    title: str = ""
    employer: str = ""
    location: str = ""
    salary: str = ""
    description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    sector: str = ""


class _GeneratedJobs(BaseModel):
    jobs: list[_GeneratedJob] = Field(min_length=1, max_length=8)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+]+", " ", text.lower()).strip()


def _profile_blob(profile: Profile) -> str:
    bits = [
        profile.summary,
        " ".join(profile.skills),
        " ".join(profile.certifications),
        " ".join(g.qualification for g in profile.education),
        " ".join(f"{language.language} {language.level}" for language in profile.languages),
    ]
    for exp in profile.experience:
        bits.append(f"{exp.title} {exp.employer} {exp.country} {' '.join(exp.achievements)}")
    return _norm(" ".join(bits))


def _overlap(skill: str, blob: str) -> bool:
    tokens = [t for t in _norm(skill).split() if len(t) > 2]
    if not tokens:
        return _norm(skill) in blob
    return all(t in blob for t in tokens) or _norm(skill) in blob


def deterministic_skill_score(profile: Profile, job: SeedJob) -> dict[str, Any]:
    """Pure-Python overlap score used before (and without) the LLM."""
    blob = _profile_blob(profile)
    matched: list[str] = []
    missing: list[str] = []
    for skill in job.required_skills:
        if _overlap(skill, blob):
            matched.append(skill)
        else:
            missing.append(skill)
    nice_hit = [s for s in job.nice_to_have if _overlap(s, blob)]
    req_n = max(len(job.required_skills), 1)
    nice_n = max(len(job.nice_to_have), 1)
    score = int(round(100 * (len(matched) / req_n) * 0.75 + 100 * (len(nice_hit) / nice_n) * 0.25))
    score = max(0, min(100, score))
    if score >= 70:
        verdict = "relevant"
    elif score >= 40:
        verdict = "partially_relevant"
    else:
        verdict = "not_relevant"
    return {
        "score": score,
        "verdict": verdict,
        "matched": matched,
        "missing": missing,
        "nice_hit": nice_hit,
    }


def _evidence_for(skill: str, profile: Profile) -> str:
    needle = _norm(skill)
    for exp in profile.experience:
        hay = _norm(f"{exp.title} {' '.join(exp.achievements)}")
        if needle in hay or any(t in hay for t in needle.split() if len(t) > 3):
            return f"{exp.title} at {exp.employer}: {exp.achievements[0] if exp.achievements else exp.title}"
    for s in profile.skills:
        if _norm(s) in needle or needle in _norm(s):
            return f"Listed skill: {s}"
    return f"Mentioned in profile summary or skills ({skill})"


def fetch_reed_jobs(keywords: str, location: str) -> list[SeedJob]:
    """Optional Reed.co.uk search. Logs and skips the live results on error."""
    settings = get_settings()
    if not settings.has_reed:
        return []
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://www.reed.co.uk/api/1.0/search",
                params={"keywords": keywords, "locationName": location, "resultsToTake": 8},
                auth=(settings.reed_api_key, ""),
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reed API failed; continuing with generated role suggestions: %s", exc)
        return []
    jobs: list[SeedJob] = []
    for i, row in enumerate(results):
        desc = row.get("jobDescription") or row.get("description") or ""
        jobs.append(
            SeedJob(
                id=f"reed-{row.get('jobId', i)}",
                title=row.get("jobTitle") or "Vacancy",
                employer=row.get("employerName") or "Employer",
                location=row.get("locationName") or location,
                salary=str(row.get("minimumSalary") or row.get("maximumSalary") or "See advert"),
                description=desc[:1200],
                required_skills=[],
                nice_to_have=[],
                requirements=[],
                sector="reed",
            )
        )
    return jobs


def generate_job_suggestions(profile: Profile, target_role: str | None = None) -> list[SeedJob]:
    """Generate candidate-tailored role ideas using the configured LLM."""
    user = (
        f"Preferred language: {profile.preferred_language}\n"
        f"Simple English: {profile.simple_english}\n"
        f"Target role: {target_role or 'No target role selected'}\n"
        f"PROFILE:\n{profile.model_dump_json()}"
    )
    generated = llm.complete_json(
        prompts.JOB_SUGGESTIONS_SYSTEM,
        user,
        _GeneratedJobs,
        temperature=0.4,
    )
    return [
        SeedJob(
            id=f"ai-suggestion-{index}",
            title=job.title or "Suggested role",
            employer="",
            location=profile.location or job.location or "United Kingdom",
            salary="Not specified — verify independently",
            description=job.description,
            required_skills=job.required_skills or profile.skills[:4],
            nice_to_have=job.nice_to_have,
            requirements=job.requirements,
            sector="ai-generated",
        )
        for index, job in enumerate(generated.jobs, start=1)
    ]


def _apply_llm_judgement(profile: Profile, job: SeedJob, base: dict[str, Any]) -> JobMatch:
    user = (
        f"Preferred language: {profile.preferred_language}\n"
        f"Simple English: {profile.simple_english}\n"
        f"Deterministic score: {base['score']} verdict={base['verdict']}\n"
        f"PROFILE:\n{profile.model_dump_json()}\n\nJOB:\n{job.model_dump_json()}"
    )
    try:
        judged = llm.complete_json(prompts.JOB_MATCH_SYSTEM, user, _LlmMatch, temperature=0.2)
        verdict = judged.verdict
        if verdict not in {"relevant", "partially_relevant", "not_relevant"}:
            verdict = base["verdict"]
        score = max(0, min(100, judged.relevancy_score or base["score"]))
        matched = judged.matched_skills or [
            SkillEvidence(skill=s, evidence=_evidence_for(s, profile)) for s in base["matched"]
        ]
        gaps = judged.gaps or [
            GapItem(skill=s, label="missing", note="Not found in the CV") for s in base["missing"]
        ]
        return JobMatch(
            job=job,
            relevancy_score=score,
            verdict=verdict,  # type: ignore[arg-type]
            matched_skills=matched,
            gaps=gaps,
            reasoning=judged.reasoning,
            must_haves=judged.must_haves or job.required_skills,
            nice_to_haves=judged.nice_to_haves or job.nice_to_have,
            keywords_for_ATS=judged.keywords_for_ATS,
            red_flags=judged.red_flags,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM job judgement failed: %s", exc)
        return JobMatch(
            job=job,
            relevancy_score=base["score"],
            verdict=base["verdict"],
            matched_skills=[
                SkillEvidence(skill=s, evidence=_evidence_for(s, profile)) for s in base["matched"]
            ],
            gaps=[GapItem(skill=s, label="missing") for s in base["missing"]],
            reasoning="Scored from skill overlap in your profile (LLM judgement unavailable).",
            must_haves=job.required_skills,
            nice_to_haves=job.nice_to_have,
        )


def match_jobs(profile: Profile, target_role: str | None = None) -> list[JobMatch]:
    """Match generated role suggestions and optional live Reed vacancies."""
    jobs = generate_job_suggestions(profile, target_role)
    keywords = target_role or (profile.experience[0].title if profile.experience else "healthcare assistant")
    location = profile.location.split(",")[0] if profile.location else "Manchester"
    jobs = jobs + fetch_reed_jobs(keywords, location)

    ranked: list[tuple[int, SeedJob, dict[str, Any]]] = []
    for job in jobs:
        base = deterministic_skill_score(profile, job)
        boost = 8 if target_role and target_role.lower() in job.title.lower() else 0
        ranked.append((min(100, base["score"] + boost), job, base))
    ranked.sort(key=lambda x: x[0], reverse=True)

    top8 = ranked[:8]
    judged = [_apply_llm_judgement(profile, job, base) for _, job, base in top8]
    judged.sort(key=lambda m: m.relevancy_score, reverse=True)
    return judged[:5]


def analyze_jd(req: AnalyzeJdRequest) -> JobMatch:
    """Match the profile against a pasted job description."""
    fake = SeedJob(
        id="pasted-jd",
        title="Pasted job description",
        employer="Employer in advert",
        location="",
        salary="",
        description=req.job_description[:8000],
        required_skills=[],
        nice_to_have=[],
        requirements=[],
        sector="pasted",
    )
    user = (
        f"Preferred language: {req.preferred_language}\n"
        f"Simple English: {req.simple_english}\n"
        f"PROFILE:\n{req.profile.model_dump_json()}\n\nJOB DESCRIPTION:\n{req.job_description[:8000]}"
    )
    try:
        judged = llm.complete_json(prompts.JD_ANALYZE_SYSTEM, user, _LlmMatch, temperature=0.2)
        verdict = judged.verdict if judged.verdict in {"relevant", "partially_relevant", "not_relevant"} else "partially_relevant"
        fake.required_skills = judged.must_haves
        fake.nice_to_have = judged.nice_to_haves
        return JobMatch(
            job=fake,
            relevancy_score=max(0, min(100, judged.relevancy_score)),
            verdict=verdict,  # type: ignore[arg-type]
            matched_skills=judged.matched_skills,
            gaps=judged.gaps,
            reasoning=judged.reasoning,
            must_haves=judged.must_haves,
            nice_to_haves=judged.nice_to_haves,
            keywords_for_ATS=judged.keywords_for_ATS,
            red_flags=judged.red_flags,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("JD analysis failed: %s", exc)
        base = deterministic_skill_score(req.profile, fake)
        return JobMatch(
            job=fake,
            relevancy_score=base["score"],
            verdict="partially_relevant",
            reasoning="Could not fully analyse the advert. Paste again or try with an API key.",
        )
