from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LitmusBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Role(str, Enum):
    APPLICANT = "applicant"
    RECRUITER = "recruiter"
    SYSTEM = "system"


class CandidateStatus(str, Enum):
    SUBMITTED = "submitted"
    ASSESSMENT_READY = "assessment_ready"
    ASSESSMENT_COMPLETED = "assessment_completed"
    SCORED = "scored"


class VerificationConfidence(str, Enum):
    VERIFIED = "verified"
    PLAUSIBLE = "plausible"
    UNVERIFIABLE = "unverifiable"
    FLAGGED = "flagged"


class PipelineTopic(str, Enum):
    RESUME_PARSED = "resume.parsed"
    FIT_SCORED = "fit.scored"
    VERIFICATION_COMPLETE = "verification.complete"
    ASSESSMENT_COMPLETE = "assessment.complete"
    FAIRNESS_ADJUSTED = "fairness.adjusted"
    SCORE_FINAL = "score.final"


class CandidateLinks(LitmusBaseModel):
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None

    @field_validator("github_url", "linkedin_url", "portfolio_url")
    @classmethod
    def validate_https_urls(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not value.startswith("https://"):
            raise ValueError("Only HTTPS URLs are accepted")
        return value


class ExperienceEntry(LitmusBaseModel):
    title: str
    company: str
    years: float = Field(ge=0)
    description: str = Field(max_length=2000)


class EducationEntry(LitmusBaseModel):
    institution: str
    degree: str
    year: str | None = None


class ResumeSubmission(LitmusBaseModel):
    candidate_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    links: CandidateLinks = Field(default_factory=CandidateLinks)


class JobPostingCreate(LitmusBaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str) -> str:
        cleaned = CONTROL_CHAR_PATTERN.sub("", value).strip()
        if len(cleaned) > 10000:
            raise ValueError("Job description exceeds 10,000 characters")
        return cleaned


class JobPosting(LitmusBaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    recruiter_id: str
    title: str
    description: str
    created_at: datetime = Field(default_factory=utc_now)


class ParsedResume(LitmusBaseModel):
    candidate_id: UUID
    job_id: UUID
    name: str
    email: str
    resume_text: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    links: CandidateLinks = Field(default_factory=CandidateLinks)
    claimed_seniority: str = Field(default="unknown", max_length=100)
    created_at: datetime = Field(default_factory=utc_now)


class ResumeParsedEvent(LitmusBaseModel):
    topic: PipelineTopic = Field(default=PipelineTopic.RESUME_PARSED)
    candidate_id: UUID
    job_id: UUID
    parsed_resume: ParsedResume


class FitScoreResult(LitmusBaseModel):
    topic: PipelineTopic = Field(default=PipelineTopic.FIT_SCORED)
    candidate_id: UUID
    job_id: UUID
    fit_score: float = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    seniority_match: str = Field(default="unknown", max_length=100)
    rationale_summary: str = Field(default="", max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)


class VerificationEvidence(LitmusBaseModel):
    source: str
    summary: str = Field(max_length=1000)


class VerificationResult(LitmusBaseModel):
    topic: PipelineTopic = Field(default=PipelineTopic.VERIFICATION_COMPLETE)
    candidate_id: UUID
    job_id: UUID
    confidence_per_skill: dict[str, VerificationConfidence] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0, le=100)
    flagged_inconsistencies: list[str] = Field(default_factory=list)
    sources_checked: list[str] = Field(default_factory=list)
    evidence: list[VerificationEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class FairnessAdjustment(LitmusBaseModel):
    topic: PipelineTopic = Field(default=PipelineTopic.FAIRNESS_ADJUSTED)
    candidate_id: UUID
    job_id: UUID
    adjusted: bool
    verification_weight: float = Field(ge=0, le=1)
    assessment_weight: float = Field(ge=0, le=1)
    fairness_note: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)


class AssessmentQuestion(LitmusBaseModel):
    question_id: UUID = Field(default_factory=uuid4)
    prompt: str = Field(min_length=1, max_length=1000)
    focus_area: str = Field(min_length=1, max_length=100)


class AssessmentQuestionSet(LitmusBaseModel):
    candidate_id: UUID
    job_id: UUID
    questions: list[AssessmentQuestion] = Field(min_length=1, max_length=8)
    created_at: datetime = Field(default_factory=utc_now)


class AssessmentAnswer(LitmusBaseModel):
    question_id: UUID
    response: str = Field(min_length=1, max_length=2000)


class AssessmentSubmission(LitmusBaseModel):
    candidate_id: UUID
    job_id: UUID
    answers: list[AssessmentAnswer] = Field(min_length=1, max_length=8)


class GradedAnswer(LitmusBaseModel):
    question_id: UUID
    score: float = Field(ge=0, le=10)
    reasoning: str = Field(max_length=1000)


class AssessmentResult(LitmusBaseModel):
    topic: PipelineTopic = Field(default=PipelineTopic.ASSESSMENT_COMPLETE)
    candidate_id: UUID
    job_id: UUID
    overall_score: float = Field(ge=0, le=100)
    graded_answers: list[GradedAnswer] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class CandidateScore(LitmusBaseModel):
    candidate_id: UUID
    job_id: UUID
    fit_score: float = Field(ge=0, le=100)
    verification_score: float = Field(ge=0, le=100)
    assessment_score: float = Field(ge=0, le=100)
    final_score: float = Field(ge=0, le=100)
    fairness_note: str | None = Field(default=None, max_length=1000)
    status: CandidateStatus = CandidateStatus.SCORED
    created_at: datetime = Field(default_factory=utc_now)


class FinalScoreEvent(LitmusBaseModel):
    topic: PipelineTopic = Field(default=PipelineTopic.SCORE_FINAL)
    score: CandidateScore


class CandidateListResponse(LitmusBaseModel):
    job_id: UUID
    candidates: list[CandidateScore] = Field(default_factory=list)


class JobCreateResponse(LitmusBaseModel):
    job: JobPosting


class ApplicationAcceptedResponse(LitmusBaseModel):
    candidate_id: UUID
    job_id: UUID
    status: CandidateStatus
    message: str


class ClaudeExtractionResult(LitmusBaseModel):
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    claimed_seniority: str = Field(default="unknown")


class ClaudeFitAnalysis(LitmusBaseModel):
    fit_score: float = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    seniority_match: str = Field(default="unknown")
    rationale_summary: str = Field(default="", max_length=1000)


class ClaudeVerificationAnalysis(LitmusBaseModel):
    confidence_per_skill: dict[str, VerificationConfidence] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0, le=100)
    flagged_inconsistencies: list[str] = Field(default_factory=list)
    evidence: list[VerificationEvidence] = Field(default_factory=list)


class ClaudeAssessmentQuestionResult(LitmusBaseModel):
    questions: list[AssessmentQuestion] = Field(min_length=1, max_length=8)


class ClaudeAssessmentGradeResult(LitmusBaseModel):
    graded_answers: list[GradedAnswer] = Field(default_factory=list)
    overall_score: float = Field(ge=0, le=100)


class HealthResponse(LitmusBaseModel):
    status: str
    service: str
    details: dict[str, Any] = Field(default_factory=dict)
