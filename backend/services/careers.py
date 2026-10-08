"""Career path suggestions."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend import llm, prompts
from backend.models import CareerOptionsResponse, CareerPath, Profile

logger = logging.getLogger("pathway.careers")


class _Paths(BaseModel):
    paths: list[CareerPath] = Field(default_factory=list)


def _fallback_paths(profile: Profile) -> list[CareerPath]:
    primary_title = (profile.experience[0].title if profile.experience else None) or (profile.skills[0] + " Specialist" if profile.skills else "Professional")
    skills_list = profile.skills if profile.skills else ["Problem Solving", "Communication", "Teamwork"]
    skills_str = ", ".join(skills_list[:5])

    return [
        CareerPath(
            title=f"{primary_title} (Direct / Core Route)",
            why_it_fits=f"Leverages your background and core skills in {skills_str}.",
            transferable_skills=skills_list[:6],
            skill_gaps=["UK Industry Best Practices", "Local Network & Market Standards"],
            typical_salary_range_gbp="£32,000 – £48,000",
            entry_route=f"Apply directly to {primary_title} roles across UK companies.",
            time_to_ready="Ready to apply immediately",
            regulated_profession=False,
            regulation_note="Standard UK professional role.",
            difficulty="med",
            first_three_steps=[
                "Tailor your UK-style CV emphasizing key achievements in your field",
                "Search UK job portals for relevant vacancy listings",
                "Connect with UK recruiters and industry peers on LinkedIn",
            ],
        ),
        CareerPath(
            title=f"{primary_title} Associate / Bridge Role",
            why_it_fits="A quick stepping stone into UK workplaces while building local experience and network.",
            transferable_skills=skills_list[:4],
            skill_gaps=["UK Workplace Tools"],
            typical_salary_range_gbp="£25,000 – £32,000",
            entry_route="Apply for associate, support, or junior positions in your domain.",
            time_to_ready="1–2 weeks",
            regulated_profession=False,
            regulation_note="",
            difficulty="low",
            first_three_steps=[
                "Identify entry-level or associate vacancies matching your skill set",
                "Highlight transferable technical and practical skills in your application",
                "Prepare for practical, scenario-based interviews",
            ],
        ),
        CareerPath(
            title=f"Operations & Technical Specialist in {primary_title}",
            why_it_fits="Applies your subject-matter expertise in an operational or analytical capacity.",
            transferable_skills=skills_list[:5],
            skill_gaps=["Advanced Domain Systems"],
            typical_salary_range_gbp="£28,000 – £38,000",
            entry_route="Apply for coordinator, operations, or specialist posts.",
            time_to_ready="1–4 weeks",
            regulated_profession=False,
            regulation_note="",
            difficulty="med",
            first_three_steps=[
                "Review popular UK software and tools in your industry",
                "Prepare concise summaries of major past achievements",
                "Target medium-to-large UK employers",
            ],
        ),
        CareerPath(
            title=f"Senior {primary_title} (Growth Route)",
            why_it_fits="Longer-term career progression into leadership or senior specialist roles.",
            transferable_skills=skills_list[:6],
            skill_gaps=["UK Professional Certification / Lead Accreditation"],
            typical_salary_range_gbp="£45,000 – £65,000+",
            entry_route="Progress through proven UK workplace achievements and certifications.",
            time_to_ready="6–12 months",
            regulated_profession=False,
            regulation_note="",
            difficulty="high",
            first_three_steps=[
                "Build a track record of high-impact project delivery",
                "Consider UK professional certifications in your discipline",
                "Develop leadership and cross-functional team skills",
            ],
        ),
    ]


def suggest_paths(profile: Profile) -> CareerOptionsResponse:
    """Return 4–6 realistic UK career paths."""
    user = (
        f"Preferred language: {profile.preferred_language}\n"
        f"Simple English: {profile.simple_english}\n\n"
        f"PROFILE JSON:\n{profile.model_dump_json()}"
    )
    try:
        parsed = llm.complete_json(
            prompts.CAREER_OPTIONS_SYSTEM, user, _Paths, temperature=0.2
        )
        paths = parsed.paths[:6]
        if len(paths) >= 4:
            return CareerOptionsResponse(paths=paths)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Career options LLM failed: %s", exc)
    return CareerOptionsResponse(paths=_fallback_paths(profile))
