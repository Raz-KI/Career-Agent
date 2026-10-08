"""Pydantic schemas for PathWay API requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    error: str
    detail: str = ""


class ExperienceItem(BaseModel):
    title: str = ""
    employer: str = ""
    country: str = ""
    years: str = ""
    achievements: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    qualification: str = ""
    institution: str = ""
    country: str = ""
    year: str = ""


class LanguageItem(BaseModel):
    language: str = ""
    level: str = ""


class Profile(BaseModel):
    name: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    gaps_or_breaks: list[str] = Field(default_factory=list)
    location: str = ""
    constraints: list[str] = Field(default_factory=list)
    preferred_language: str = "en"
    simple_english: bool = False
    raw_text: str = ""


class ProfileFromTextRequest(BaseModel):
    text: str
    preferred_language: str = "en"
    simple_english: bool = False


class CoachingContext(BaseModel):
    profile: Profile
    preferred_language: str = "en"
    simple_english: bool = False
    target_role: str | None = None
    job: dict[str, Any] | None = None
    job_description: str | None = None
    user_message: str | None = None


class CareerPath(BaseModel):
    title: str
    why_it_fits: str
    transferable_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    typical_salary_range_gbp: str = ""
    entry_route: str = ""
    time_to_ready: str = ""
    regulated_profession: bool = False
    regulation_note: str = ""
    difficulty: Literal["low", "med", "high"] = "med"
    first_three_steps: list[str] = Field(default_factory=list)


class CareerOptionsResponse(BaseModel):
    paths: list[CareerPath]


class SeedJob(BaseModel):
    id: str
    title: str
    employer: str
    location: str
    salary: str
    description: str
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    sector: str = ""


class SkillEvidence(BaseModel):
    skill: str
    evidence: str


class GapItem(BaseModel):
    skill: str
    label: Literal["missing", "weak_evidence"]
    note: str = ""


class JobMatch(BaseModel):
    job: SeedJob
    relevancy_score: int = Field(ge=0, le=100)
    verdict: Literal["relevant", "partially_relevant", "not_relevant"]
    matched_skills: list[SkillEvidence] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    reasoning: str = ""
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    keywords_for_ATS: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class JobMatchRequest(BaseModel):
    profile: Profile
    target_role: str | None = None
    preferred_language: str = "en"
    simple_english: bool = False


class AnalyzeJdRequest(BaseModel):
    profile: Profile
    job_description: str
    preferred_language: str = "en"
    simple_english: bool = False


class GapPlanItem(BaseModel):
    gap: str
    how_to_address: str
    quick_win_this_week: str
    longer_term_option: str
    free_resource_suggestion: str


class GapPlanRequest(BaseModel):
    profile: Profile
    gaps: list[GapItem] | list[str]
    target_role: str | None = None
    preferred_language: str = "en"
    simple_english: bool = False


class CvChange(BaseModel):
    original: str
    revised: str
    reason: str
    accepted: bool = True


class TailoredCv(BaseModel):
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    translation: str | None = None


class ClaimCheck(BaseModel):
    claim: str
    supported: bool
    evidence_or_reason: str = ""


class TruthfulnessReport(BaseModel):
    claims: list[ClaimCheck] = Field(default_factory=list)
    verified_count: int = 0
    total_count: int = 0
    unsupported: list[ClaimCheck] = Field(default_factory=list)


class TailorCvRequest(BaseModel):
    profile: Profile
    job: dict[str, Any] | None = None
    job_description: str | None = None
    preferred_language: str = "en"
    simple_english: bool = False


class TailorCvResponse(BaseModel):
    cv: TailoredCv
    changes: list[CvChange] = Field(default_factory=list)
    truthfulness: TruthfulnessReport
    translation: str | None = None


class CoverLetterRequest(BaseModel):
    profile: Profile
    job: dict[str, Any] | None = None
    job_description: str | None = None
    preferred_language: str = "en"
    simple_english: bool = False


class CoverLetterResponse(BaseModel):
    letter: str
    translation: str | None = None
    truthfulness: TruthfulnessReport


class ExportRequest(BaseModel):
    kind: Literal["cv", "cover_letter", "handoff"]
    cv: TailoredCv | None = None
    letter: str | None = None
    handoff_text: str | None = None
    name: str = "PathWay"
    excluded_claims: list[str] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    type: Literal[
        "motivation",
        "competency",
        "situational",
        "technical",
        "gap_or_background",
    ]
    question: str
    why_they_ask: str = ""
    ideal_answer_outline_using_STAR: str = ""
    translation: str | None = None


class InterviewQuestionsRequest(BaseModel):
    profile: Profile
    job: dict[str, Any] | None = None
    job_description: str | None = None
    preferred_language: str = "en"
    simple_english: bool = False


class InterviewStartRequest(BaseModel):
    profile: Profile
    job: dict[str, Any] | None = None
    job_description: str | None = None
    difficulty: Literal["friendly", "realistic", "tough"] = "realistic"
    english_level: Literal["simple", "standard"] = "standard"
    num_questions: int = 5
    language_for_feedback: str = "en"
    preferred_language: str = "en"
    simple_english: bool = False


class InterviewAnswerRequest(BaseModel):
    session_id: str
    answer: str


class InterviewTurnResponse(BaseModel):
    session_id: str
    interviewer: str
    question_index: int
    total_questions: int
    done: bool = False
    translation: str | None = None


class StarBreakdown(BaseModel):
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    missing_parts: list[str] = Field(default_factory=list)


class AnswerScores(BaseModel):
    relevance: int = 0
    structure_STAR: int = 0
    specificity: int = 0
    clarity: int = 0
    confidence_language: int = 0


class PerAnswerEval(BaseModel):
    question: str
    answer: str
    scores: AnswerScores = Field(default_factory=AnswerScores)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    star_breakdown: StarBreakdown = Field(default_factory=StarBreakdown)
    improved_sample_answer: str = ""
    perfect_candidate_answer: str = ""
    tone_and_delivery_tips: str = ""


class OverallEval(BaseModel):
    score: int = 0
    top_3_strengths: list[str] = Field(default_factory=list)
    top_3_improvements: list[str] = Field(default_factory=list)
    filler_words_count: int = 0
    avg_answer_length_words: int = 0
    next_practice_focus: str = ""


class InterviewEvalResponse(BaseModel):
    per_answer: list[PerAnswerEval] = Field(default_factory=list)
    overall: OverallEval = Field(default_factory=OverallEval)


class VoiceTtsRequest(BaseModel):
    text: str
    voice_id: str | None = None
    speed: float | None = None
    language_code: str | None = None


class SafetyResult(BaseModel):
    triggered: bool = False
    category: str | None = None
    message: str = ""
    resources: list[str] = Field(default_factory=list)
    offer_handoff: bool = True


class HandoffRequest(BaseModel):
    profile: Profile
    chosen_path: CareerPath | None = None
    matches: list[JobMatch] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    interview_eval: InterviewEvalResponse | None = None
    safety_flags: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    consent: bool = False
    preferred_language: str = "en"
    simple_english: bool = False


class HandoffResponse(BaseModel):
    summary: str
    translation: str | None = None
