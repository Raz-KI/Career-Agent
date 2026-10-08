"""Truthfulness guard: invented UK credentials must be flagged."""

from backend.models import Profile
from backend.services.application import heuristic_unsupported, run_truthfulness_guard


def _nurse() -> Profile:
    return Profile(
        name="Olena",
        summary="Nurse in Ukraine for 12 years. Not on the UK NMC register.",
        skills=["patient care"],
        certifications=["Ukrainian nursing diploma"],
        location="Manchester",
    )


def test_heuristic_catches_invented_nmc():
    profile = _nurse()
    text = "I am an NMC registered Band 5 nurse with a current NMC PIN."
    hits = heuristic_unsupported(profile, text)
    assert hits, "Expected invented NMC registration to be flagged"
    assert any(not h.supported for h in hits)


def test_guard_with_mocked_llm(monkeypatch):
    from backend.models import ClaimCheck
    from backend.services import application as app_mod
    from pydantic import BaseModel

    class Fake(BaseModel):
        claims: list[ClaimCheck]

    def fake_json(*_a, **_k):
        return Fake(
            claims=[
                ClaimCheck(
                    claim="Bachelor of Nursing from Oxford",
                    supported=False,
                    evidence_or_reason="Qualification not in profile",
                )
            ]
        )

    monkeypatch.setattr(app_mod.llm, "complete_json", fake_json)
    report = run_truthfulness_guard(_nurse(), "Educated at Oxford with a Bachelor of Nursing.")
    assert report.unsupported
    assert report.verified_count == 0
    assert any("Oxford" in c.claim or "Qualification" in c.evidence_or_reason for c in report.unsupported)
