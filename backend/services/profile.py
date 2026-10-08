"""CV parsing and profile extraction."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from backend import llm, prompts
from backend.models import Profile

logger = logging.getLogger("pathway.profile")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEMO_PATH = DATA_DIR / "demo_profile.json"


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    """Extract plain text from PDF, DOCX, or TXT uploads."""
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    return data.decode("utf-8", errors="replace")


def load_demo_profile() -> Profile:
    """Return the seeded Ukrainian nurse persona."""
    payload = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    return Profile.model_validate(payload)


def profile_from_text(
    text: str,
    *,
    preferred_language: str = "en",
    simple_english: bool = False,
) -> Profile:
    """Ask the LLM to structure a profile, falling back to a minimal parse."""
    user = (
        f"Preferred language: {preferred_language}\n"
        f"Simple English: {simple_english}\n\n"
        f"SOURCE TEXT:\n{text[:12000]}"
    )
    try:
        profile = llm.complete_json(
            prompts.PROFILE_EXTRACT_SYSTEM,
            user,
            Profile,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Profile LLM extract failed: %s", exc)
        profile = Profile(summary=text[:400], raw_text=text, skills=[])
    profile.preferred_language = preferred_language
    profile.simple_english = simple_english
    profile.raw_text = text[:15000]
    return profile
