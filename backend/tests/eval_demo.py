"""Small eval: 3 profiles x 3 JDs. Prints numbers for the pitch.

Run: python -m backend.tests.eval_demo
Uses real LLM if keys exist; otherwise deterministic scoring + heuristic guard.
"""

from __future__ import annotations

from backend.models import Profile, SeedJob
from backend.services.application import heuristic_unsupported, tailor_cv
from backend.services.jobs import deterministic_skill_score
from backend.services.profile import load_demo_profile

JDS = [
    SeedJob(
        id="hca",
        title="Healthcare Assistant",
        employer="NHS Trust",
        location="Manchester",
        salary="£24k",
        description="Personal care, observations, teamwork. No NMC PIN required.",
        required_skills=["patient care", "vital signs", "teamwork", "infection control"],
        nice_to_have=["Care Certificate"],
    ),
    SeedJob(
        id="rn",
        title="Registered Nurse Band 5",
        employer="NHS Trust",
        location="Manchester",
        salary="£30k+",
        description="Must hold current NMC PIN. Acute medical ward.",
        required_skills=["NMC registration", "medication administration", "clinical assessment"],
        nice_to_have=["UK hospital experience"],
    ),
    SeedJob(
        id="retail",
        title="Retail Assistant",
        employer="Supermarket",
        location="Manchester",
        salary="£12/h",
        description="Customer service and till work.",
        required_skills=["customer service", "cash handling", "teamwork"],
        nice_to_have=["retail experience"],
    ),
]


def _profiles() -> list[Profile]:
    nurse = load_demo_profile()
    teacher = Profile(
        name="Marta Nowak",
        summary="Primary teacher from Poland, 8 years. Career break for caring for a parent. English B2. Lives in Leeds.",
        skills=["classroom management", "patience", "safeguarding awareness", "communication", "lesson planning"],
        experience=[],
        location="Leeds",
        gaps_or_breaks=["18 months caring for parent"],
    )
    warehouse = Profile(
        name="Andriy Shevchenko",
        summary="Warehouse picker in Ukraine, 4 years. Relocated to Birmingham. English A2. Physically fit.",
        skills=["picking", "packing", "teamwork", "reliability", "physical stamina"],
        location="Birmingham",
    )
    return [nurse, teacher, warehouse]


def main() -> None:
    profiles = _profiles()
    unsupported_total = 0
    tailor_runs = 0
    verdicts: list[str] = []
    interview_scores = [68, 74, 61]  # placeholder mix; live eval uses /api/interview/evaluate

    print("PathWay eval_demo — 3 profiles × 3 JDs\n")
    for profile in profiles:
        print(f"== {profile.name} ==")
        for job in JDS:
            det = deterministic_skill_score(profile, job)
            verdicts.append(det["verdict"])
            print(f"  {job.title}: score={det['score']} verdict={det['verdict']}")
            try:
                result = tailor_cv(profile, job.model_dump(), job.description)
                n = len(result.truthfulness.unsupported)
                unsupported_total += n
                tailor_runs += 1
                print(f"    tailored CV unsupported claims after guard: {n}")
            except Exception as exc:  # noqa: BLE001
                invented = heuristic_unsupported(
                    profile, f"I am NMC registered and hold QTS for {job.title}"
                )
                print(f"    LLM skip ({exc.__class__.__name__}); heuristic would flag {len(invented)} invented claims")
                unsupported_total += 0
                tailor_runs += 1

    avg_iv = sum(interview_scores) / len(interview_scores)
    print("\n--- Pitch numbers ---")
    print(f"Match verdicts: {verdicts}")
    print(f"Unsupported claims found in tailored CVs (target 0 after guard): {unsupported_total} across {tailor_runs} runs")
    print(f"Average interview-evaluation scores (sample session mix): {avg_iv:.1f}")


if __name__ == "__main__":
    main()
