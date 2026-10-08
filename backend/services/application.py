"""CV tailoring, cover letters, truthfulness guard, and .docx export."""

from __future__ import annotations

import io
import logging
import re
from typing import Any

from docx import Document
from docx.shared import Pt
from pydantic import BaseModel, Field

from backend import llm, prompts
from backend.models import (
    ClaimCheck,
    CoverLetterResponse,
    CvChange,
    GapItem,
    GapPlanItem,
    Profile,
    TailoredCv,
    TailorCvResponse,
    TruthfulnessReport,
)

logger = logging.getLogger("pathway.application")


class _GapPlan(BaseModel):
    items: list[GapPlanItem] = Field(default_factory=list)


class _TailorOut(BaseModel):
    cv: TailoredCv
    changes: list[CvChange] = Field(default_factory=list)
    translation: str | None = None


class _LetterOut(BaseModel):
    letter: str = ""
    translation: str | None = None


class _ClaimsOut(BaseModel):
    claims: list[ClaimCheck] = Field(default_factory=list)


INVENTED_PATTERNS = [
    (r"\bnmc\b", "UK NMC registration"),
    (r"\bqts\b", "QTS / UK teaching status"),
    (r"\bdbs\s+(check|certificate)\b", "existing DBS certificate"),
    (r"\bright to work (confirmed|verified)\b", "right-to-work confirmation"),
]


def _profile_positively_claims(blob: str, token_pattern: str) -> bool:
    """True only if the original profile asserts the credential (not a denial)."""
    if not re.search(token_pattern, blob, flags=re.I):
        return False
    for m in re.finditer(token_pattern, blob, flags=re.I):
        window = blob[max(0, m.start() - 48) : m.end() + 24]
        if re.search(r"\b(not|no|without|n't|unregistered|pending|do not)\b", window, flags=re.I):
            continue
        return True
    return False


def heuristic_unsupported(profile: Profile, text: str) -> list[ClaimCheck]:
    """Catch common invented UK credentials even without an LLM."""
    blob = profile.model_dump_json().lower()
    found: list[ClaimCheck] = []
    for pattern, label in INVENTED_PATTERNS:
        if re.search(pattern, text, flags=re.I) and not _profile_positively_claims(blob, pattern):
            found.append(
                ClaimCheck(
                    claim=label,
                    supported=False,
                    evidence_or_reason="This UK credential is not in the original profile.",
                )
            )
    return found


def gap_plan(
    profile: Profile,
    gaps: list[GapItem] | list[str],
    target_role: str | None,
) -> list[GapPlanItem]:
    """Practical, low-cost ways to address each gap."""
    normalised: list[str] = []
    for g in gaps:
        normalised.append(g.skill if isinstance(g, GapItem) else str(g))
    user = (
        f"Preferred language: {profile.preferred_language}\nSimple English: {profile.simple_english}\n"
        f"Target role: {target_role or ''}\nGaps: {normalised}\nPROFILE:\n{profile.model_dump_json()}"
    )
    try:
        parsed = llm.complete_json(prompts.GAP_PLAN_SYSTEM, user, _GapPlan, temperature=0.2)
        if parsed.items:
            return parsed.items
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gap plan LLM failed: %s", exc)
    items: list[GapPlanItem] = []
    for g in normalised:
        items.append(
            GapPlanItem(
                gap=g,
                how_to_address=f"Show related experience you already have, then learn the UK-specific part of '{g}'.",
                quick_win_this_week="Write three bullet points of real examples. Practise saying them in Simple English.",
                longer_term_option="Ask a college, council, or National Careers Service adviser about free training.",
                free_resource_suggestion=f"Search for '{g}' on National Careers Service / GOV.UK. Do not pay for unofficial 'guaranteed job' courses.",
            )
        )
    return items


def _strip_excluded(cv: TailoredCv, excluded: list[str]) -> TailoredCv:
    lowered = [e.lower() for e in excluded if e]

    def ok(text: str) -> bool:
        t = text.lower()
        return not any(e in t for e in lowered)

    cv.summary = cv.summary if ok(cv.summary) else ""
    cv.skills = [s for s in cv.skills if ok(s)]
    for exp in cv.experience:
        exp.achievements = [a for a in exp.achievements if ok(a)]
    return cv


def run_truthfulness_guard(profile: Profile, documents: str) -> TruthfulnessReport:
    """Second LLM pass plus heuristic checks. Unsupported claims must be dropped from downloads by default."""
    user = f"ORIGINAL PROFILE JSON:\n{profile.model_dump_json()}\n\nGENERATED DOCUMENTS:\n{documents[:12000]}"
    claims: list[ClaimCheck] = []
    try:
        parsed = llm.complete_json(prompts.TRUTHFULNESS_SYSTEM, user, _ClaimsOut, temperature=0.2)
        claims.extend(parsed.claims)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Truthfulness LLM failed: %s", exc)
    claims.extend(heuristic_unsupported(profile, documents))
    # de-dupe by claim text
    uniq: dict[str, ClaimCheck] = {}
    for c in claims:
        uniq[c.claim.strip()[:180]] = c
    claims = list(uniq.values())
    unsupported = [c for c in claims if not c.supported]
    verified = [c for c in claims if c.supported]
    return TruthfulnessReport(
        claims=claims,
        verified_count=len(verified),
        total_count=len(claims),
        unsupported=unsupported,
    )


def tailor_cv(
    profile: Profile,
    job: dict[str, Any] | None,
    job_description: str | None,
) -> TailorCvResponse:
    """ATS-oriented rewrite that must not invent facts."""
    user = (
        f"Preferred language: {profile.preferred_language}\nSimple English: {profile.simple_english}\n"
        f"PROFILE:\n{profile.model_dump_json()}\nJOB:\n{job}\nJD:\n{(job_description or '')[:6000]}"
    )
    try:
        parsed = llm.complete_json(prompts.TAILOR_CV_SYSTEM, user, _TailorOut, temperature=0.2)
        cv, changes, translation = parsed.cv, parsed.changes, parsed.translation
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tailor CV LLM failed: %s", exc)
        cv = TailoredCv(
            summary=profile.summary,
            skills=list(profile.skills),
            experience=list(profile.experience),
            education=list(profile.education),
        )
        changes = [
            CvChange(
                original=profile.summary,
                revised=profile.summary,
                reason="LLM unavailable — original wording kept so nothing is invented.",
            )
        ]
        translation = None
    doc_text = cv.model_dump_json()
    report = run_truthfulness_guard(profile, doc_text)
    excluded = [c.claim for c in report.unsupported]
    cv = _strip_excluded(cv, excluded)
    return TailorCvResponse(cv=cv, changes=changes, truthfulness=report, translation=translation)


def cover_letter(
    profile: Profile,
    job: dict[str, Any] | None,
    job_description: str | None,
) -> CoverLetterResponse:
    user = (
        f"Preferred language: {profile.preferred_language}\nSimple English: {profile.simple_english}\n"
        f"PROFILE:\n{profile.model_dump_json()}\nJOB:\n{job}\nJD:\n{(job_description or '')[:6000]}"
    )
    try:
        parsed = llm.complete_json(prompts.COVER_LETTER_SYSTEM, user, _LetterOut, temperature=0.7)
        letter, translation = parsed.letter, parsed.translation
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cover letter LLM failed: %s", exc)
        name = profile.name or "Applicant"
        role = (job or {}).get("title") or "this role"
        letter = (
            f"Dear Hiring Manager,\n\nMy name is {name}. I am applying for {role}. "
            f"{profile.summary}\n\nI do not claim UK professional registration I do not hold. "
            "I would welcome the chance to discuss how my real experience could help your team.\n\nYours sincerely,\n"
            f"{name}"
        )
        translation = None
    report = run_truthfulness_guard(profile, letter)
    # Remove unsupported sentences from the downloadable default
    for claim in report.unsupported:
        letter = letter.replace(claim.claim, "")
    return CoverLetterResponse(letter=letter.strip(), translation=translation, truthfulness=report)


def _add_heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14)


def build_cv_docx(cv: TailoredCv, name: str, excluded_claims: list[str] | None = None) -> bytes:
    """ATS-friendly single-column CV."""
    if excluded_claims:
        cv = _strip_excluded(cv.model_copy(deep=True), excluded_claims)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    title = doc.add_paragraph()
    run = title.add_run(name or "Curriculum Vitae")
    run.bold = True
    run.font.size = Pt(18)
    _add_heading(doc, "Personal statement")
    doc.add_paragraph(cv.summary)
    _add_heading(doc, "Key skills")
    doc.add_paragraph(", ".join(cv.skills))
    _add_heading(doc, "Experience")
    for exp in cv.experience:
        head = doc.add_paragraph()
        r = head.add_run(f"{exp.title} — {exp.employer} ({exp.country}) {exp.years}")
        r.bold = True
        for a in exp.achievements:
            doc.add_paragraph(a, style="List Bullet")
    _add_heading(doc, "Education")
    for ed in cv.education:
        doc.add_paragraph(f"{ed.qualification}, {ed.institution}, {ed.country} ({ed.year})")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_letter_docx(letter: str, name: str) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    heading = doc.add_paragraph()
    run = heading.add_run(f"Cover letter — {name}")
    run.bold = True
    run.font.size = Pt(14)
    for para in letter.split("\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_handoff_docx(summary: str) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    h = doc.add_paragraph()
    r = h.add_run("PathWay adviser brief")
    r.bold = True
    r.font.size = Pt(16)
    for para in summary.split("\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
