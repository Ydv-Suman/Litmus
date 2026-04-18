import logging
import os
import secrets
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Generator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.applications_received import ApplicationReceived
from models.job_listing import JobListing
from s3_config.s3_helper import delete_file_from_s3, upload_file_to_s3
from service.github_analyser import analyze_github_profile
from service.assessment_generator import generate_technical_assessment
from service.email_notify import send_html_email
from service.pipeline_screening import compute_pipeline_screening
from service.resume_parser import structure_resume_from_pdf_bytes
from service.resume_reality_match import compute_resume_reality_match


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


def normalize_optional_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().rstrip("/")
    return cleaned or None


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


def build_integrity_error_message(exc: IntegrityError) -> str:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name:
        normalized_constraint = constraint_name.lower()
        if "job" in normalized_constraint:
            return "The selected job opening is invalid."

    error_text = str(getattr(exc.orig, "pgerror", "") or exc.orig).lower()
    if "foreign key" in error_text or "job_id" in error_text:
        return "The selected job opening is invalid."

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


def _assessment_base_url() -> str:
    return os.getenv("PUBLIC_APP_BASE_URL", os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")).strip().rstrip("/")


def _build_assessment_email_html(public_name: str, assessment_url: str, job_title: str) -> str:
    return f"""\
<html><body style="font-family: system-ui, sans-serif; line-height: 1.5;">
  <p>Hi {public_name},</p>
  <p>Your application for <strong>{job_title}</strong> has passed the initial resume screening.</p>
  <p>Complete your technical assessment using the secure link below (Part 1: knowledge MCQs, Part 2: coding challenge). Save this email for your records.</p>
  <p><a href="{assessment_url}">{assessment_url}</a></p>
  <p>Good luck,<br/>Litmus Hiring</p>
</body></html>"""


@router.post("")
def submit_application(
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    resume: UploadFile = File(...),
    job_id: int = Form(...),
    github_url: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    db: Session = Depends(get_db),
):
    resume_file_name = validate_resume_file(resume)

    try:
        resume.file.seek(0)
    except (AttributeError, OSError):
        pass
    resume_bytes = resume.file.read()
    if not resume_bytes:
        raise HTTPException(status_code=400, detail="Resume file is empty.")

    cleaned_full_name = require_text(full_name, "Full name")
    cleaned_email = require_text(email, "Email").lower()
    cleaned_phone = require_text(phone, "Phone")
    cleaned_github_url = normalize_optional_url(github_url)
    cleaned_linkedin = (
        normalize_url(require_text(linkedin_url, "LinkedIn URL"))
        if linkedin_url and linkedin_url.strip()
        else None
    )

    resume_parsed: dict[str, Any] | None = None
    resume_parse_error: str | None = None
    try:
        resume_parsed = structure_resume_from_pdf_bytes(resume_bytes)
    except Exception as exc:
        resume_parse_error = str(exc)
        logger.exception("Resume LLM parsing failed; application will still be stored.")

    job = db.query(JobListing).filter(JobListing.id == job_id).first()
    reality_match: dict[str, Any] | None = None
    reality_match_error: str | None = None
    if not job:
        reality_match_error = "Job listing is missing or inactive."
    elif resume_parsed:
        try:
            reality_match = compute_resume_reality_match(job, resume_parsed)
        except Exception as exc:
            reality_match_error = str(exc)
            logger.exception("Resume vs job scoring failed.")
    else:
        reality_match_error = "Skipped until resume is parsed successfully."

    github_analysis: dict[str, Any] | None = None
    github_analysis_error: str | None = None
    if cleaned_github_url:
        try:
            github_analysis = analyze_github_profile(
                cleaned_github_url,
                resume_data=resume_parsed,
            )
        except Exception as exc:
            github_analysis_error = str(exc)
            logger.exception("GitHub credibility scoring failed.")
    else:
        github_analysis_error = "Skipped because no GitHub URL was provided."
    screening = compute_pipeline_screening(reality_match, cleaned_linkedin)

    uploaded_resume = upload_file_to_s3(
        BytesIO(resume_bytes),
        file_name=resume_file_name,
        folder="resumes",
        content_type=resume.content_type,
    )

    now = datetime.now(timezone.utc)
    assessment_token: str | None = None
    assessment_payload: dict[str, Any] | None = None
    assessment_url: str | None = None
    email_sent = False
    passed_screening = bool(screening and screening.get("screening_passed"))

    if passed_screening and job:
        try:
            assessment_payload = generate_technical_assessment(job)
            assessment_token = secrets.token_urlsafe(32)
            assessment_url = f"{_assessment_base_url()}/assessment/{assessment_token}"
        except Exception as exc:
            cleanup_uploaded_resume(uploaded_resume["key"])
            logger.exception("Assessment generation failed after screening passed.")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to generate the technical assessment. Please try again later. ({exc})",
            ) from exc

    application = ApplicationReceived(
        full_name=cleaned_full_name,
        email=cleaned_email,
        phone=cleaned_phone,
        resume_file_name=uploaded_resume["key"],
        github_url=cleaned_github_url,
        linkedin_url=cleaned_linkedin,
        job_id=job_id,
        pipeline_resume_points=screening["pipeline_resume_points"],
        pipeline_linkedin_points=screening["pipeline_linkedin_points"],
        pipeline_total=screening["pipeline_total"],
        pipeline_max=screening["pipeline_max"],
        screening_passed=passed_screening,
        assessment_token=assessment_token,
        assessment_payload=assessment_payload,
        assessment_sent_at=None,
        status="assessment_invited" if passed_screening and assessment_token else "screening_failed",
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
        if isinstance(exc, OperationalError):
            logger.exception("Database unavailable during application submission.")
            raise HTTPException(
                status_code=503,
                detail="Database is unavailable. Please try again in a moment.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="Failed to submit application.",
        ) from exc

    response: dict[str, Any] = {
        "message": "Application submitted successfully."
        if passed_screening
        else "Application received. You did not meet the minimum screening score to proceed to the technical assessment.",
        "passed_screening": passed_screening,
        "application_id": application.id,
        "resume_url": uploaded_resume["url"],
        "status": application.status,
        "resume_parsed": resume_parsed,
        "resume_parse_error": resume_parse_error,
        "resume_vs_reality": reality_match,
        "resume_vs_reality_error": reality_match_error,
        "github_analysis": github_analysis,
        "github_analysis_error": github_analysis_error,
        "pipeline_screening": screening,
    }

    if not passed_screening:
        return response

    assert assessment_url and assessment_token and job is not None

    email_sent = send_html_email(
        to_address=cleaned_email,
        subject=f"Technical assessment — {job.title}",
        html_body=_build_assessment_email_html(cleaned_full_name.split()[0], assessment_url, job.title),
        text_body=f"You passed resume screening for {job.title}. Open your assessment: {assessment_url}",
    )

    if email_sent:
        application.assessment_sent_at = now
        try:
            db.commit()
        except SQLAlchemyError:
            logger.exception("Failed to persist assessment_sent_at.")
    else:
        response["email_note"] = (
            "Assessment link could not be emailed (configure SendGrid in backend/.env). "
            "Use assessment_url from this response."
        )

    response["assessment_url"] = assessment_url
    response["email_sent"] = email_sent
    response["message"] = (
        "Application submitted and technical assessment generated. Check your email for the link."
        if email_sent
        else "Application submitted. Use the assessment URL below to continue."
    )
    return response
