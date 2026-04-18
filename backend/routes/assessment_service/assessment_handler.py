"""Fetch and submit technical assessments by secret token."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models.applications_received import ApplicationReceived
from service.assessment_generator import strip_assessment_answers_for_candidate

router = APIRouter(prefix="/assessment", tags=["assessment"])


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{token}")
def get_assessment_for_candidate(
    token: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = (
        db.query(ApplicationReceived)
        .filter(
            ApplicationReceived.assessment_token == token,
            ApplicationReceived.is_deleted.is_(False),
        )
        .first()
    )
    if not row or not row.assessment_payload:
        raise HTTPException(status_code=404, detail="Assessment not found or no longer available.")

    return {
        "application_id": row.id,
        "job_id": row.job_id,
        "assessment": strip_assessment_answers_for_candidate(row.assessment_payload),
        "already_submitted": row.assessment_submitted_at is not None,
    }


class AssessmentSubmitRequest(BaseModel):
    answers: dict[str, str]


@router.post("/{token}/submit")
def submit_assessment(
    token: str,
    payload: AssessmentSubmitRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = (
        db.query(ApplicationReceived)
        .filter(
            ApplicationReceived.assessment_token == token,
            ApplicationReceived.is_deleted.is_(False),
        )
        .first()
    )
    if not row or not row.assessment_payload:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    if row.assessment_submitted_at is not None:
        raise HTTPException(status_code=409, detail="Assessment already submitted.")

    mcq_questions = row.assessment_payload.get("part1_mcq", [])
    points_each = (
        row.assessment_payload.get("grading_notes", {}).get("mcq_points_each") or 5
    )

    correct_count = sum(
        1
        for q in mcq_questions
        if str(q.get("id")) in payload.answers
        and payload.answers[str(q.get("id"))].upper() == str(q.get("correct", "")).upper()
    )
    mcq_score = correct_count * points_each

    row.assessment_score = float(mcq_score)
    row.assessment_submitted_at = datetime.now(timezone.utc)
    row.status = "assessment_completed"
    db.commit()

    return {
        "message": "Assessment submitted successfully.",
        "mcq_score": mcq_score,
        "mcq_total": len(mcq_questions) * points_each,
        "correct": correct_count,
        "total_questions": len(mcq_questions),
    }
