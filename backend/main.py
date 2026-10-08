"""PathWay FastAPI application."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config import get_settings
from backend.llm import LlmError
from backend.models import (
    AnalyzeJdRequest,
    CoverLetterRequest,
    ErrorBody,
    ExportRequest,
    GapPlanRequest,
    HandoffRequest,
    InterviewAnswerRequest,
    InterviewQuestionsRequest,
    InterviewStartRequest,
    JobMatchRequest,
    Profile,
    ProfileFromTextRequest,
    VoiceTtsRequest,
)
from backend.services import application as application_svc
from backend.services import careers as careers_svc
from backend.services import interview as interview_svc
from backend.services import jobs as jobs_svc
from backend.services import profile as profile_svc
from backend.services import safety as safety_svc
from backend.services import voice as voice_svc
from backend.services.interview import SESSIONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pathway")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="PathWay", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SafetyCheckRequest(BaseModel):
    text: str
    preferred_language: str = "en"


class CareerOptionsRequest(BaseModel):
    profile: Profile
    preferred_language: str | None = None
    simple_english: bool | None = None


class GapPlanBody(GapPlanRequest):
    pass


class InterviewEvalBody(BaseModel):
    session_id: str


class DeleteBody(BaseModel):
    session_id: str | None = None


def _err(status: int, error: str, detail: str = "") -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorBody(error=error, detail=detail).model_dump())


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return _err(500, "server_error", str(exc))


@app.get("/api/health")
# Loads the env
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "app": "PathWay",
        "llm": s.has_llm,
        "elevenlabs": s.has_elevenlabs,
        "reed": s.has_reed,
        "model": s.llm_model,
    }


@app.get("/api/profile/demo")
def demo_profile() -> dict:
    return profile_svc.load_demo_profile().model_dump()


@app.post("/api/profile/from_text")
def profile_from_text(body: ProfileFromTextRequest) -> dict:
    flag = safety_svc.classify(body.text, body.preferred_language)
    if flag.triggered and flag.category in {"mental_health_distress", "safeguarding_exploitation", "domestic_abuse"}:
        return {"safety": flag.model_dump(), "profile": None}
    profile = profile_svc.profile_from_text(
        body.text,
        preferred_language=body.preferred_language,
        simple_english=body.simple_english,
    )
    return {"profile": profile.model_dump(), "safety": flag.model_dump()}


@app.post("/api/profile/upload")
async def profile_upload(
    file: UploadFile = File(...),
    preferred_language: str = Form("en"),
    simple_english: bool = Form(False),
) -> dict:
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(status_code=400, detail="File too large")
    text = profile_svc.extract_text_from_bytes(file.filename or "cv.txt", data)
    if not text.strip():
        return _err(400, "empty_cv", "Could not read text from that file.")
    profile = profile_svc.profile_from_text(
        text,
        preferred_language=preferred_language,
        simple_english=simple_english,
    )
    return {"profile": profile.model_dump()}


@app.post("/api/careers/options")
def career_options(body: CareerOptionsRequest) -> dict:
    if body.preferred_language:
        body.profile.preferred_language = body.preferred_language
    if body.simple_english is not None:
        body.profile.simple_english = body.simple_english
    return careers_svc.suggest_paths(body.profile).model_dump()


@app.post("/api/jobs/match")
def jobs_match(body: JobMatchRequest) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    try:
        matches = jobs_svc.match_jobs(body.profile, body.target_role)
    except LlmError as exc:
        raise HTTPException(status_code=503, detail=f"Could not generate job suggestions: {exc}") from exc
    return {"matches": [m.model_dump() for m in matches]}


@app.post("/api/jobs/analyze_jd")
def analyze_jd(body: AnalyzeJdRequest) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    match = jobs_svc.analyze_jd(body)
    return match.model_dump()


@app.post("/api/application/gap_plan")
def gap_plan(body: GapPlanBody) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    items = application_svc.gap_plan(body.profile, body.gaps, body.target_role)
    return {"items": [i.model_dump() for i in items]}


@app.post("/api/application/tailor_cv")
def tailor_cv(body: CoverLetterRequest) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    return application_svc.tailor_cv(body.profile, body.job, body.job_description).model_dump()


@app.post("/api/application/cover_letter")
def cover_letter(body: CoverLetterRequest) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    return application_svc.cover_letter(body.profile, body.job, body.job_description).model_dump()


@app.post("/api/application/export")
def export_doc(body: ExportRequest) -> Response:
    if body.kind == "cv":
        if not body.cv:
            return _err(400, "missing_cv", "No CV to export")
        data = application_svc.build_cv_docx(body.cv, body.name, body.excluded_claims)
        filename = "pathway-cv.docx"
    elif body.kind == "cover_letter":
        data = application_svc.build_letter_docx(body.letter or "", body.name)
        filename = "pathway-cover-letter.docx"
    else:
        data = application_svc.build_handoff_docx(body.handoff_text or "")
        filename = "pathway-adviser-brief.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/interview/questions")
def interview_questions(body: InterviewQuestionsRequest) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    qs = interview_svc.generate_questions(body.profile, body.job, body.job_description)
    return {"questions": [q.model_dump() for q in qs]}


@app.post("/api/interview/start")
def interview_start(body: InterviewStartRequest) -> dict:
    body.profile.preferred_language = body.preferred_language
    body.profile.simple_english = body.simple_english
    turn = interview_svc.start_session(
        body.profile,
        body.job,
        body.job_description,
        difficulty=body.difficulty,
        english_level=body.english_level,
        num_questions=body.num_questions,
        language_for_feedback=body.language_for_feedback or body.preferred_language,
    )
    return turn.model_dump()


@app.post("/api/interview/answer")
def interview_answer(body: InterviewAnswerRequest) -> dict:
    flag = safety_svc.classify(body.answer)
    if flag.triggered:
        return {"safety": flag.model_dump(), "interviewer": flag.message, "done": True}
    try:
        turn = interview_svc.answer_turn(body.session_id, body.answer)
    except KeyError:
        return _err(404, "unknown_session", "Start the interview again.")
    return turn.model_dump()


@app.post("/api/interview/evaluate")
def interview_evaluate(body: InterviewEvalBody) -> dict:
    try:
        return interview_svc.evaluate(body.session_id).model_dump()
    except KeyError:
        return _err(404, "unknown_session", "Start the interview again.")


@app.post("/api/voice/stt")
async def voice_stt(
    file: UploadFile = File(...),
    language_code: str = Form(""),
) -> dict:
    data = await file.read()
    try:
        result = voice_svc.stt(
            data,
            file.filename or "audio.webm",
            file.content_type or "audio/webm",
            language_code or None,
        )
    except voice_svc.VoiceError as exc:
        return _err(503, "voice_unavailable", str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("STT failed: %s", exc)
        return _err(502, "stt_failed", "Could not transcribe audio. Please type instead.")
    return result


@app.post("/api/voice/tts")
def voice_tts(body: VoiceTtsRequest) -> Response:
    try:
        audio = voice_svc.tts(body.text, body.voice_id, body.speed)
    except voice_svc.VoiceError as exc:
        return _err(503, "voice_unavailable", str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("TTS failed")
        detail = str(exc)[:300] or "Could not speak. Please read the text."
        api_key = get_settings().elevenlabs_api_key
        if api_key:
            detail = detail.replace(api_key, "[redacted]")
        return _err(502, "tts_failed", detail)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/safety/check")
def safety_check(body: SafetyCheckRequest) -> dict:
    return safety_svc.classify(body.text, body.preferred_language).model_dump()


@app.post("/api/handoff/summary")
def handoff(body: HandoffRequest) -> dict:
    try:
        return safety_svc.handoff_summary(body).model_dump()
    except ValueError as exc:
        return _err(400, "consent_required", str(exc))


@app.post("/api/session/delete")
def delete_data(body: DeleteBody) -> dict:
    if body.session_id:
        interview_svc.delete_session(body.session_id)
    else:
        interview_svc.clear_all()
    return {"ok": True, "sessions": len(SESSIONS)}


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
