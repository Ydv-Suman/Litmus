import logging
import os
import secrets
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Generator

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
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
from service.linkedin_scraper import analyze_linkedin_profile
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


def get_active_job_or_404(db: Session, job_id: int) -> JobListing:
    job = (
        db.query(JobListing)
        .filter(
            JobListing.id == job_id,
            JobListing.is_active.is_(True),
            JobListing.is_deleted.is_(False),
        )
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="The selected job opening is invalid.")
    return job


def _resume_url_value(resume_parsed: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(resume_parsed, dict):
        return None
    value = resume_parsed.get(key)
    if not value or not str(value).strip():
        return None
    return str(value).strip()


def _persist_submission_response_payload(
    db: Session,
    application: ApplicationReceived,
    payload: dict[str, Any],
) -> None:
    application.submission_response_payload = payload
    try:
        db.commit()
        db.refresh(application)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist application submission response payload.")


def _process_application_submission_in_background(
    *,
    application_id: int,
    resume_bytes: bytes,
    cleaned_full_name: str,
    cleaned_email: str,
    cleaned_github_url: str | None,
    cleaned_linkedin_url: str | None,
    job_id: int,
) -> None:
    db = SessionLocal()
    try:
        application = (
            db.query(ApplicationReceived)
            .filter(ApplicationReceived.id == application_id, ApplicationReceived.is_deleted.is_(False))
            .first()
        )
        if application is None:
            logger.warning("Background submission processing skipped because application %s no longer exists.", application_id)
            return

        job = get_active_job_or_404(db, job_id)

        resume_parsed: dict[str, Any] | None = None
        resume_parse_error: str | None = None
        try:
            resume_parsed = structure_resume_from_pdf_bytes(resume_bytes)
        except Exception as exc:  # noqa: BLE001
            resume_parse_error = str(exc)
            logger.exception("Resume LLM parsing failed in background processing.")

        resolved_github_url = cleaned_github_url or normalize_optional_url(_resume_url_value(resume_parsed, "github_url"))
        resolved_linkedin_url = cleaned_linkedin_url or (
            normalize_url(_resume_url_value(resume_parsed, "linkedin_url"))
            if _resume_url_value(resume_parsed, "linkedin_url")
            else None
        )

        reality_match: dict[str, Any] | None = None
        reality_match_error: str | None = None
        if resume_parsed:
            try:
                reality_match = compute_resume_reality_match(job, resume_parsed)
            except Exception as exc:  # noqa: BLE001
                reality_match_error = str(exc)
                logger.exception("Resume vs job scoring failed in background processing.")
        else:
            reality_match_error = "Skipped until resume is parsed successfully."

        github_analysis: dict[str, Any] | None = None
        github_analysis_error: str | None = None
        if resolved_github_url:
            try:
                github_analysis = analyze_github_profile(
                    resolved_github_url,
                    resume_data=resume_parsed,
                )
            except Exception as exc:  # noqa: BLE001
                github_analysis_error = str(exc)
                logger.exception("GitHub credibility scoring failed in background processing.")
        else:
            github_analysis_error = "Skipped because no GitHub URL was provided."

        linkedin_analysis: dict[str, Any] | None = None
        linkedin_analysis_error: str | None = None
        if resolved_linkedin_url:
            try:
                linkedin_analysis = analyze_linkedin_profile(
                    resolved_linkedin_url,
                    resume_data=resume_parsed,
                    job=job,
                )
            except Exception as exc:  # noqa: BLE001
                linkedin_analysis_error = str(exc)
                logger.exception("LinkedIn credibility scoring failed in background processing.")
        else:
            linkedin_analysis_error = "Skipped because no LinkedIn URL was provided."

        screening = compute_pipeline_screening(
            reality_match,
            github_analysis,
            linkedin_analysis,
        )

        passed_screening = bool(screening and screening.get("screening_passed"))
        assessment_token: str | None = None
        assessment_payload: dict[str, Any] | None = None
        assessment_url: str | None = None
        email_sent = False
        assessment_sent_at = None

        if passed_screening:
            try:
                assessment_payload = generate_technical_assessment(job)
                assessment_token = secrets.token_urlsafe(32)
                assessment_url = f"{_assessment_base_url()}/assessment/{assessment_token}"
            except Exception as exc:  # noqa: BLE001
                logger.exception("Assessment generation failed in background processing.")
                passed_screening = False
                github_analysis_error = github_analysis_error
                linkedin_analysis_error = linkedin_analysis_error
                screening = {
                    **screening,
                    "screening_passed": False,
                }
                assessment_payload = None
                assessment_token = None
                assessment_url = None
                resume_parse_error = resume_parse_error or f"Assessment generation failed: {exc}"

        application.github_url = resolved_github_url
        application.linkedin_url = resolved_linkedin_url
        application.pipeline_resume_points = screening["pipeline_resume_points"]
        application.pipeline_resume_max = screening["pipeline_resume_max"]
        application.pipeline_github_points = screening["pipeline_github_points"]
        application.pipeline_github_max = screening["pipeline_github_max"]
        application.pipeline_linkedin_points = screening["pipeline_linkedin_points"]
        application.pipeline_linkedin_max = screening["pipeline_linkedin_max"]
        application.pipeline_total = screening["pipeline_total"]
        application.pipeline_max = screening["pipeline_max"]
        application.screening_passed = passed_screening
        application.assessment_token = assessment_token
        application.assessment_payload = assessment_payload
        application.assessment_sent_at = None
        application.status = "assessment_invited" if passed_screening and assessment_token else "screening_failed"
        application.resume_detail = {"parsed": resume_parsed, "reality_match": reality_match}
        application.github_detail = github_analysis
        application.linkedin_detail = {
            "analysis": linkedin_analysis,
            "screening": screening.get("linkedin_detail"),
        }

        response: dict[str, Any] = {
            "message": "Application processing completed.",
            "passed_screening": passed_screening,
            "application_id": application.id,
            "resume_url": None,
            "status": application.status,
            "resume_parsed": resume_parsed,
            "resume_parse_error": resume_parse_error,
            "resume_vs_reality": reality_match,
            "resume_vs_reality_error": reality_match_error,
            "github_analysis": github_analysis,
            "github_analysis_error": github_analysis_error,
            "pipeline_screening": screening,
            "linkedin_analysis": linkedin_analysis,
            "linkedin_analysis_error": linkedin_analysis_error,
        }

        try:
            db.commit()
            db.refresh(application)
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Failed to persist background screening results for application %s.", application.id)
            return

        if passed_screening and assessment_url:
            email_sent = send_html_email(
                to_address=cleaned_email,
                subject=f"Technical assessment — {job.title}",
                html_body=_build_assessment_email_html(cleaned_full_name.split()[0], assessment_url, job.title),
                text_body=f"You passed resume screening for {job.title}. Open your assessment: {assessment_url}",
            )
            if email_sent:
                assessment_sent_at = datetime.now(timezone.utc)
                application.assessment_sent_at = assessment_sent_at
                try:
                    db.commit()
                    db.refresh(application)
                except SQLAlchemyError:
                    db.rollback()
                    logger.exception("Failed to persist assessment_sent_at for application %s.", application.id)
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

        _persist_submission_response_payload(db, application, response)
    except HTTPException:
        logger.exception("Background processing hit an HTTPException for application %s.", application_id)
    except Exception:  # noqa: BLE001
        logger.exception("Background processing failed for application %s.", application_id)
    finally:
        db.close()


@router.post("")
def submit_application(
    background_tasks: BackgroundTasks,
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
    submitted_github_url = normalize_optional_url(github_url)
    submitted_linkedin_url = (
        normalize_url(require_text(linkedin_url, "LinkedIn URL"))
        if linkedin_url and linkedin_url.strip()
        else None
    )
    job = get_active_job_or_404(db, job_id)

    uploaded_resume = upload_file_to_s3(
        BytesIO(resume_bytes),
        file_name=resume_file_name,
        folder="resumes",
        content_type=resume.content_type,
    )

    cleaned_github_url = submitted_github_url
    cleaned_linkedin_url = submitted_linkedin_url

    application = ApplicationReceived(
        full_name=cleaned_full_name,
        email=cleaned_email,
        phone=cleaned_phone,
        resume_file_name=uploaded_resume["key"],
        github_url=cleaned_github_url,
        linkedin_url=cleaned_linkedin_url,
        job_id=job_id,
        pipeline_resume_points=None,
        pipeline_resume_max=None,
        pipeline_github_points=None,
        pipeline_github_max=None,
        pipeline_linkedin_points=None,
        pipeline_linkedin_max=None,
        pipeline_total=None,
        pipeline_max=None,
        screening_passed=None,
        assessment_token=None,
        assessment_payload=None,
        assessment_sent_at=None,
        status="submitted",
        resume_detail=None,
        github_detail=None,
        linkedin_detail=None,
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
        "message": "Application submitted. We will contact you for further steps through email.",
        "application_id": application.id,
        "resume_url": uploaded_resume["url"],
        "status": application.status,
    }
    _persist_submission_response_payload(db, application, response)
    background_tasks.add_task(
        _process_application_submission_in_background,
        application_id=application.id,
        resume_bytes=resume_bytes,
        cleaned_full_name=cleaned_full_name,
        cleaned_email=cleaned_email,
        cleaned_github_url=cleaned_github_url,
        cleaned_linkedin_url=cleaned_linkedin_url,
        job_id=job_id,
    )
    return response
