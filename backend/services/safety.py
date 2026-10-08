"""Handoff / escalation detection. Keyword rules first, then a fast LLM classifier."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel

from backend import llm, prompts
from backend.models import HandoffRequest, HandoffResponse, SafetyResult

logger = logging.getLogger("pathway.safety")
GUIDANCE_PATH = Path(__file__).resolve().parent.parent / "data" / "uk_guidance.md"

IMMIGRATION = re.compile(
    r"\b(visa|asylum|ilr|indefinite leave|immigration|right to work (for me|advice)|sponsor licence|home office decision)\b",
    re.I,
)
EXPLOITATION = re.compile(
    r"\b(passport.{0,40}(held|keep|took|withhold|withheld)|(withhold|withheld|kept|keep).{0,30}passport|"
    r"unpaid (work|trial shift)|modern slavery|they took my documents|threaten.{0,20}deport)\b",
    re.I,
)
ABUSE = re.compile(r"\b(domestic abuse|my (husband|partner|wife) (hits|hit|beats)|i am not safe at home)\b", re.I)
DISTRESS = re.compile(
    r"\b(suicid|kill myself|end my life|self[- ]harm|want to die|can't go on)\b",
    re.I,
)
FABRICATE = re.compile(
    r"\b(make up|invent|fake (cv|certificate|reference|qualification)|lie on my (cv|application)|pretend i (have|worked))\b",
    re.I,
)
DISCRIMINATION = re.compile(r"\b(racist|racism|they won't hire (ukrain|foreign)|discriminat)\b", re.I)


MESSAGES = {
    "immigration_legal": (
        "I cannot give immigration or visa advice. I am not a lawyer or OISC adviser. "
        "Please check GOV.UK (search 'right to work' or 'asylum support') or speak to a regulated adviser. "
        "Citizens Advice can help you find someone. I can still help with CVs and interview practice."
    ),
    "safeguarding_exploitation": (
        "I am concerned about your safety at work. An employer should not keep your passport. "
        "If you are in danger now, call 999. "
        "You can also contact the Modern Slavery helpline 08000 121 700, ACAS 0300 123 1100, or Citizens Advice. "
        "A human adviser should hear this — I can prepare a summary if you consent."
    ),
    "domestic_abuse": (
        "I am sorry you are going through this. If you are in danger, call 999. "
        "You can contact the National Domestic Abuse Helpline 0808 2000 247. "
        "I can help with job search, but a trained human should support you on safety."
    ),
    "mental_health_distress": (
        "I am glad you told me. You deserve support. If you are in danger, call 999. "
        "Samaritans is free on 116 123, any time. I am an AI career tool and cannot replace a person. "
        "Would you like a summary for a human adviser?"
    ),
    "fabricate_credentials": (
        "I cannot invent experience, qualifications, or references. UK employers can withdraw offers if information is false. "
        "I can help you describe your real work clearly, explain a career gap honestly, and show transferable skills."
    ),
    "discrimination": (
        "Unequal treatment at work may be something ACAS or Citizens Advice can help with. "
        "I cannot give legal advice. I can still help you prepare applications."
    ),
}

RESOURCES = {
    "immigration_legal": ["GOV.UK", "Citizens Advice", "OISC-regulated adviser"],
    "safeguarding_exploitation": ["999 if in danger", "Modern Slavery helpline 08000 121 700", "ACAS 0300 123 1100"],
    "domestic_abuse": ["999", "National Domestic Abuse Helpline 0808 2000 247"],
    "mental_health_distress": ["999", "Samaritans 116 123"],
    "fabricate_credentials": ["Be honest on applications", "National Careers Service"],
    "discrimination": ["ACAS", "Citizens Advice", "GOV.UK discrimination at work"],
}


class _Cls(BaseModel):
    triggered: bool = False
    category: str = "none"
    brief_reason: str = ""


def _keyword_category(text: str) -> str | None:
    if DISTRESS.search(text):
        return "mental_health_distress"
    if EXPLOITATION.search(text):
        return "safeguarding_exploitation"
    if ABUSE.search(text):
        return "domestic_abuse"
    if FABRICATE.search(text):
        return "fabricate_credentials"
    if IMMIGRATION.search(text):
        return "immigration_legal"
    if DISCRIMINATION.search(text):
        return "discrimination"
    return None


def classify(text: str, preferred_language: str = "en") -> SafetyResult:
    """Return a SafetyResult. Keyword hits always trigger; LLM used as a second opinion."""
    if not text or not text.strip():
        return SafetyResult(triggered=False)
    category = _keyword_category(text)
    if category is None:
        try:
            parsed = llm.complete_json(
                prompts.SAFETY_CLASSIFIER_SYSTEM,
                f"Language: {preferred_language}\nMESSAGE:\n{text[:4000]}",
                _Cls,
                temperature=0.1,
            )
            if parsed.triggered and parsed.category not in (None, "none", ""):
                category = parsed.category
        except Exception as exc:  # noqa: BLE001
            logger.info("Safety LLM skipped: %s", exc)
    if not category:
        return SafetyResult(triggered=False)
    return SafetyResult(
        triggered=True,
        category=category,
        message=MESSAGES.get(category, MESSAGES["immigration_legal"]),
        resources=RESOURCES.get(category, ["GOV.UK", "Citizens Advice"]),
        offer_handoff=True,
    )


def employment_info_answer(question: str) -> str:
    """Grounded answers from uk_guidance.md only."""
    guidance = GUIDANCE_PATH.read_text(encoding="utf-8")
    user = f"GUIDANCE:\n{guidance}\n\nQUESTION:\n{question}"
    try:
        return llm.complete(prompts.EMPLOYMENT_INFO_SYSTEM, user, temperature=0.2, json_mode=False)
    except Exception:
        return (
            "I'm not sure from the short guidance I have. Please check GOV.UK or ACAS. "
            "I cannot give legal or immigration advice."
        )


def handoff_summary(req: HandoffRequest) -> HandoffResponse:
    if not req.consent:
        raise ValueError("Consent is required before generating an adviser summary.")
    user = (
        f"Preferred language: {req.preferred_language}\nSimple English: {req.simple_english}\n"
        f"PROFILE: {req.profile.model_dump_json()}\nPATH: {req.chosen_path}\n"
        f"MATCHES: {[m.model_dump() for m in req.matches[:5]]}\nGAPS: {req.gaps}\n"
        f"INTERVIEW: {req.interview_eval}\nFLAGS: {req.safety_flags}\nPREFS: {req.preferences}"
    )
    try:
        return llm.complete_json(prompts.HANDOFF_SYSTEM, user, HandoffResponse, temperature=0.2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Handoff LLM failed: %s", exc)
        p = req.profile
        lines = [
            f"Adviser brief for {p.name or 'the person'} ({p.location})",
            f"Summary: {p.summary}",
            f"Skills: {', '.join(p.skills)}",
            f"Chosen path: {req.chosen_path.title if req.chosen_path else 'not chosen'}",
            f"Gaps: {', '.join((g.skill if hasattr(g, 'skill') else str(g)) for g in req.gaps)}",
            f"Safety flags: {', '.join(req.safety_flags) or 'none recorded'}",
            "This brief was generated on the person's device session. Nothing was emailed.",
        ]
        return HandoffResponse(summary="\n".join(lines))
