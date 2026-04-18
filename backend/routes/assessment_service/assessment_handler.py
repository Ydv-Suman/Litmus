"""Fetch technical assessment content by secret token (MCQ answers stripped)."""

from __future__ import annotations

from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException
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
    }
