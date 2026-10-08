"""Mock interview sessions, questions, turns, and evaluation."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from backend import llm, prompts
from backend.models import (
    InterviewEvalResponse,
    InterviewQuestion,
    InterviewTurnResponse,
    OverallEval,
    PerAnswerEval,
    Profile,
)

logger = logging.getLogger("pathway.interview")

# In-memory only. Cleared on process restart.
SESSIONS: dict[str, dict[str, Any]] = {}


class _QOut(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)


class _TurnOut(BaseModel):
    interviewer: str = ""
    done: bool = False


def _fallback_questions(profile: Profile, job_title: str) -> list[InterviewQuestion]:
    title = job_title or (profile.experience[0].title if profile.experience else "this role")
    skills_str = ", ".join(profile.skills[:4]) if profile.skills else "your core skills"

    return [
        InterviewQuestion(
            type="motivation",
            question=f"Thank you for coming in today. What attracted you to apply for a {title} position in the UK?",
            why_they_ask="Evaluates your genuine interest, career direction, and understanding of the role.",
            ideal_answer_outline_using_STAR=f"State your enthusiasm for {title}, mention how your experience in {skills_str} aligns, and outline your target UK career goals.",
        ),
        InterviewQuestion(
            type="technical",
            question=f"Can you walk us through a major project or technical task you led as a {title}? What tools or methodologies did you use?",
            why_they_ask="Assesses hands-on technical competence, methodology, and problem-solving depth.",
            ideal_answer_outline_using_STAR=f"Situation: Describe project scope. Task: Your responsibility. Action: Specific technical steps using {skills_str}. Result: Measurable outcome.",
        ),
        InterviewQuestion(
            type="competency",
            question="Tell me about a time you encountered a tight deadline or high-pressure problem in your team. How did you handle it?",
            why_they_ask="UK employers look for resilience, prioritization, and effective communication under pressure.",
            ideal_answer_outline_using_STAR="Situation: High-pressure deadline. Task: Deliver key objective. Action: Prioritization, stakeholder communication, team collaboration. Result: Delivered on time.",
        ),
        InterviewQuestion(
            type="situational",
            question="If a colleague or stakeholder disagrees with your proposed solution or technical decision, how do you resolve it?",
            why_they_ask="Evaluates teamwork, diplomacy, professional communication, and conflict resolution.",
            ideal_answer_outline_using_STAR="Situation: Disagreement on approach. Task: Reach consensus. Action: Active listening, data-backed discussion, compromise. Result: Successful collaboration.",
        ),
        InterviewQuestion(
            type="gap_or_background",
            question="How are you finding adapting your skills to the UK workplace, and what professional support would help you excel?",
            why_they_ask="Tests self-awareness, adaptability, and openness to team integration.",
            ideal_answer_outline_using_STAR="Mention one real example of adapting to UK standards, highlight your eagerness to learn, and ask for clear team goals.",
        ),
    ]


def generate_questions(
    profile: Profile,
    job: dict[str, Any] | None,
    job_description: str | None,
) -> list[InterviewQuestion]:
    title = (job or {}).get("title") or "this role"
    user = (
        f"Preferred language: {profile.preferred_language}\nSimple English: {profile.simple_english}\n"
        f"PROFILE:\n{profile.model_dump_json()}\nJOB:\n{job}\nJD:\n{(job_description or '')[:4000]}"
    )
    try:
        parsed = llm.complete_json(
            prompts.INTERVIEW_QUESTIONS_SYSTEM, user, _QOut, temperature=0.3
        )
        if len(parsed.questions) >= 8:
            return parsed.questions[:10]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Interview questions LLM failed: %s", exc)
    return _fallback_questions(profile, str(title))


def start_session(
    profile: Profile,
    job: dict[str, Any] | None,
    job_description: str | None,
    *,
    difficulty: str,
    english_level: str,
    num_questions: int,
    language_for_feedback: str,
) -> InterviewTurnResponse:
    questions = generate_questions(profile, job, job_description)[: max(3, min(num_questions, 8))]
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "profile": profile.model_dump(),
        "job": job,
        "job_description": job_description,
        "difficulty": difficulty,
        "english_level": english_level,
        "language_for_feedback": language_for_feedback,
        "questions": [q.model_dump() for q in questions],
        "index": 0,
        "turns": [],
        "done": False,
    }
    q1 = questions[0].question if questions else "Why do you want this role?"
    opener = (
        "Hello, I am an AI practice interviewer for PathWay. This is not a real job interview. "
        "You can stop at any time. Let's begin. "
        f"{q1}"
    )
    SESSIONS[session_id]["turns"].append({"role": "interviewer", "text": opener})
    return InterviewTurnResponse(
        session_id=session_id,
        interviewer=opener,
        question_index=1,
        total_questions=len(questions),
        done=False,
    )


def answer_turn(session_id: str, answer: str) -> InterviewTurnResponse:
    session = SESSIONS.get(session_id)
    if not session:
        raise KeyError("Unknown interview session")
    session["turns"].append({"role": "user", "text": answer})
    questions = session["questions"]
    session["index"] += 1
    done = session["index"] >= len(questions)
    session["done"] = done
    user = (
        f"Difficulty: {session['difficulty']}\nEnglish level: {session['english_level']}\n"
        f"Question index (0-based next): {session['index']}\nDone after this?: {done}\n"
        f"Questions: {questions}\nRecent answer: {answer}\n"
        f"Transcript: {session['turns'][-8:]}"
    )
    try:
        parsed = llm.complete_json(prompts.INTERVIEW_TURN_SYSTEM, user, _TurnOut, temperature=0.7)
        text = parsed.interviewer
        done = done or parsed.done
    except Exception as exc:  # noqa: BLE001
        logger.warning("Interview turn LLM failed: %s", exc)
        if done:
            text = "Thank you. That is the end of this practice interview. I will now prepare your feedback."
        else:
            nxt = questions[session["index"]]["question"]
            text = f"Thank you. {nxt}"
    session["turns"].append({"role": "interviewer", "text": text})
    session["done"] = done
    return InterviewTurnResponse(
        session_id=session_id,
        interviewer=text,
        question_index=min(session["index"] + 1, len(questions)),
        total_questions=len(questions),
        done=done,
    )


def evaluate(session_id: str) -> InterviewEvalResponse:
    session = SESSIONS.get(session_id)
    if not session:
        raise KeyError("Unknown interview session")
    user = (
        f"Feedback language: {session.get('language_for_feedback', 'en')}\n"
        f"Questions: {session['questions']}\nTurns: {session['turns']}"
    )
    try:
        return llm.complete_json(
            prompts.INTERVIEW_EVAL_SYSTEM, user, InterviewEvalResponse, temperature=0.3
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Interview eval LLM failed: %s", exc)
        answers = [t for t in session["turns"] if t["role"] == "user"]
        per: list[PerAnswerEval] = []
        for i, ans in enumerate(answers):
            q = session["questions"][i]["question"] if i < len(session["questions"]) else "Question"
            words = len(ans["text"].split())
            per.append(
                PerAnswerEval(
                    question=q,
                    answer=ans["text"],
                    strengths=["You answered directly in your own words with relevant details."],
                    improvements=["Structure your response using STAR (Situation, Task, Action, Result) and state clear quantitative outcomes."],
                    improved_sample_answer=ans["text"] + " This resulted in a 20% increase in team efficiency.",
                    perfect_candidate_answer=f"For {q}: In my previous role, I encountered a complex requirement (Situation). My task was to deliver a scalable solution on time (Task). I collaborated with senior engineers, refactored core modules, and implemented unit tests (Action). As a result, we deployed seamlessly with zero downtime and improved system performance by 30% (Result).",
                    tone_and_delivery_tips="Maintain a steady pacing of ~130 words per minute. Take a 1-second deliberate pause before answering, use a confident and calm intonation, and avoid filler words like 'um' or 'like'.",
                )
            )
        filler = sum(ans["text"].lower().count(w) for ans in answers for w in (" um", " uh", " like,"))
        avg = int(sum(len(a["text"].split()) for a in answers) / max(len(answers), 1))
        return InterviewEvalResponse(
            per_answer=per,
            overall=OverallEval(
                score=62,
                top_3_strengths=["Showed up and practised", "Spoke about real work", "Honest about gaps"],
                top_3_improvements=["Use STAR", "Add one number", "Shorter answers"],
                filler_words_count=filler,
                avg_answer_length_words=avg,
                next_practice_focus="Practise one STAR story about a busy shift.",
            ),
        )


def delete_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)


def clear_all() -> None:
    SESSIONS.clear()
