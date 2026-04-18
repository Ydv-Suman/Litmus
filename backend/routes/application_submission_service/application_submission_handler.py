import os
import logging
from typing import Generator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.applications_received import ApplicationReceived
from s3_config.s3_helper import delete_file_from_s3, upload_file_to_s3


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/submitApplication",
    tags=["submit application"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    return cleaned


def normalize_url(value: str) -> str:
    return value.strip().rstrip("/").lower()


def validate_resume_file(resume: UploadFile) -> str:
    resume_file_name = os.path.basename(resume.filename or "").strip()
    if not resume_file_name:
        raise HTTPException(status_code=400, detail="Resume file name is required.")

    if not resume_file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    allowed_content_types = {"application/pdf", "application/x-pdf"}
    if resume.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    return resume_file_name


def ensure_unique_application_fields(
    db: Session,
    *,
    email: str,
    phone: str,
    linkedin_url: str,
) -> None:
    conflict_checks = [
        ("email", email, "An application with this email already exists."),
        ("phone", phone, "An application with this phone number already exists."),
        (
            "linkedin_url",
            linkedin_url,
            "An application with this LinkedIn URL already exists.",
        ),
    ]

    for field_name, field_value, error_message in conflict_checks:
        existing_application = (
            db.query(ApplicationReceived)
            .filter(
                func.lower(func.trim(getattr(ApplicationReceived, field_name)))
                == field_value.lower()
            )
            .first()
        )
        if existing_application:
            raise HTTPException(status_code=409, detail=error_message)


def build_integrity_error_message(exc: IntegrityError) -> str:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name:
        normalized_constraint = constraint_name.lower()
        if "email" in normalized_constraint:
            return "An application with this email already exists."
        if "phone" in normalized_constraint:
            return "An application with this phone number already exists."
        if "linkedin" in normalized_constraint:
            return "An application with this LinkedIn URL already exists."
        if "job" in normalized_constraint:
            return "The selected job opening is invalid."

    error_text = str(getattr(exc.orig, "pgerror", "") or exc.orig).lower()
    if "foreign key" in error_text or "job_id" in error_text:
        return "The selected job opening is invalid."
    if "email" in error_text:
        return "An application with this email already exists."
    if "phone" in error_text:
        return "An application with this phone number already exists."
    if "linkedin" in error_text:
        return "An application with this LinkedIn URL already exists."

    logger.exception("Unhandled integrity error during application submission.", exc_info=exc)
    return "Application data failed validation in the database."


def cleanup_uploaded_resume(s3_key: str) -> None:
    try:
        delete_file_from_s3(s3_key)
    except HTTPException as exc:
        logger.warning(
            "Failed to clean up uploaded S3 object %s after application error: %s",
            s3_key,
            exc.detail,
        )


@router.post("")
def submit_application(
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    resume: UploadFile = File(...),
    job_id: int = Form(...),
    github_url: str | None = Form(None),
    linkedin_url: str = Form(...),
    db: Session = Depends(get_db),
):
    resume_file_name = validate_resume_file(resume)

    cleaned_full_name = require_text(full_name, "Full name")
    cleaned_email = require_text(email, "Email").lower()
    cleaned_phone = require_text(phone, "Phone")
    cleaned_linkedin_url = normalize_url(require_text(linkedin_url, "LinkedIn URL"))
    ensure_unique_application_fields(
        db,
        email=cleaned_email,
        phone=cleaned_phone,
        linkedin_url=cleaned_linkedin_url,
    )
    uploaded_resume = upload_file_to_s3(
        resume,
        file_name=resume_file_name,
        folder="resumes",
        content_type=resume.content_type,
    )

    application = ApplicationReceived(
        full_name=cleaned_full_name,
        email=cleaned_email,
        phone=cleaned_phone,
        resume_file_name=uploaded_resume["key"],
        github_url=github_url.strip() if github_url else None,
        linkedin_url=cleaned_linkedin_url,
        job_id=job_id,
    )

    try:
        db.add(application)
        db.commit()
        db.refresh(application)
    except IntegrityError as exc:
        db.rollback()
        cleanup_uploaded_resume(uploaded_resume["key"])
        raise HTTPException(
            status_code=409,
            detail=build_integrity_error_message(exc),
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        cleanup_uploaded_resume(uploaded_resume["key"])
        raise HTTPException(
            status_code=500,
            detail="Failed to submit application.",
        ) from exc

    return {
        "message": "Application submitted successfully.",
        "application_id": application.id,
        "resume_url": uploaded_resume["url"],
        "status": application.status,
    }
