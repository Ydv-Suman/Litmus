from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.applications_received import ApplicationReceived
from models.hr_user import HrUser
from models.job_listing import JobListing
from security.password_helper import hash_password, verify_password


router = APIRouter(
    prefix="/hr",
    tags=["hr auth"],
)


def normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        raise ValueError("A valid email is required.")
    return cleaned


class HrSignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: str
    department: str
    phone: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return cleaned

    @field_validator("full_name", "company_name", "department")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class HrLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_hr_user_by_email(db: Session, email: str) -> HrUser | None:
    return db.query(HrUser).filter(HrUser.email == email.lower()).first()


def ensure_unique_hr_phone(db: Session, phone: str) -> None:
    existing = (
        db.query(HrUser)
        .filter(
            func.lower(func.trim(HrUser.phone)) == phone.strip().lower(),
            HrUser.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="An HR user with this phone number already exists.")


def build_hr_integrity_error_message(exc: IntegrityError) -> str:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name:
        normalized = constraint_name.lower()
        if "email" in normalized:
            return "An HR user with this email already exists."
        if "phone" in normalized:
            return "An HR user with this phone number already exists."

    error_text = str(getattr(exc.orig, "pgerror", "") or exc.orig).lower()
    if "email" in error_text:
        return "An HR user with this email already exists."
    if "phone" in error_text:
        return "An HR user with this phone number already exists."

    return "An HR user with this email already exists."


def get_active_hr_user(db: Session, user_id: int) -> HrUser:
    hr_user = db.query(HrUser).filter(HrUser.id == user_id, HrUser.is_deleted.is_(False)).first()
    if hr_user is None:
        raise HTTPException(status_code=404, detail="HR user not found.")
    return hr_user


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup_hr_user(payload: HrSignupRequest, db: Session = Depends(get_db)):
    existing_user = get_hr_user_by_email(db, payload.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="An HR user with this email already exists.")

    if payload.phone:
        ensure_unique_hr_phone(db, payload.phone)

    hr_user = HrUser(
        email=payload.email.lower(),
        password=hash_password(payload.password),
        full_name=payload.full_name,
        company_name=payload.company_name,
        department=payload.department,
        role="hr",
        phone=payload.phone,
    )

    try:
        db.add(hr_user)
        db.commit()
        db.refresh(hr_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=build_hr_integrity_error_message(exc),
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create HR user.",
        ) from exc

    # Assign unowned job listings in the same department to this HR user
    try:
        db.query(JobListing).filter(
            func.lower(JobListing.department) == hr_user.department.lower(),
            JobListing.hr_user_id.is_(None),
            JobListing.is_deleted.is_(False),
        ).update({"hr_user_id": hr_user.id}, synchronize_session=False)
        db.commit()
    except SQLAlchemyError:
        db.rollback()

    return {
        "message": "HR user created successfully.",
        "user": {
            "id": hr_user.id,
            "email": hr_user.email,
            "full_name": hr_user.full_name,
            "company_name": hr_user.company_name,
            "department": hr_user.department,
            "role": hr_user.role,
            "phone": hr_user.phone,
            "is_active": hr_user.is_active,
        },
    }


@router.post("/login")
def login_hr_user(payload: HrLoginRequest, db: Session = Depends(get_db)):
    hr_user = get_hr_user_by_email(db, payload.email)
    if hr_user is None or hr_user.is_deleted:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not hr_user.is_active:
        raise HTTPException(status_code=403, detail="HR user account is inactive.")

    if not verify_password(payload.password, hr_user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "message": "Login successful.",
        "user": {
            "id": hr_user.id,
            "email": hr_user.email,
            "full_name": hr_user.full_name,
            "company_name": hr_user.company_name,
            "department": hr_user.department,
            "role": hr_user.role,
            "phone": hr_user.phone,
            "is_active": hr_user.is_active,
        },
    }


@router.delete("/{user_id}")
def delete_hr_user(user_id: int, db: Session = Depends(get_db)):
    hr_user = get_active_hr_user(db, user_id)

    hr_user.is_deleted = True
    hr_user.is_active = False

    try:
        db.commit()
        db.refresh(hr_user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete HR user.") from exc

    return {
        "message": "HR user deleted successfully.",
        "user_id": hr_user.id,
    }


@router.get("/{user_id}/applications/{application_id}")
def get_hr_application_detail(user_id: int, application_id: int, db: Session = Depends(get_db)):
    get_active_hr_user(db, user_id)

    result = (
        db.query(ApplicationReceived, JobListing)
        .join(JobListing, ApplicationReceived.job_id == JobListing.id)
        .filter(
            ApplicationReceived.id == application_id,
            JobListing.hr_user_id == user_id,
            JobListing.is_deleted.is_(False),
            ApplicationReceived.is_deleted.is_(False),
        )
        .first()
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    application, job = result

    assessment_with_answers = None
    if application.assessment_payload:
        import copy
        payload = copy.deepcopy(application.assessment_payload)
        if application.assessment_answers:
            for q in payload.get("part1_mcq") or []:
                q["candidate_answer"] = application.assessment_answers.get(str(q.get("id")))
        assessment_with_answers = payload

    return {
        "application_id": application.id,
        "full_name": application.full_name,
        "email": application.email,
        "phone": application.phone,
        "github_url": application.github_url,
        "linkedin_url": application.linkedin_url,
        "status": application.status,
        "job": {"id": job.id, "title": job.title, "department": job.department},
        "submitted_at": application.created_at,
        "screening_passed": application.screening_passed,
        "pipeline_resume_points": application.pipeline_resume_points,
        "pipeline_linkedin_points": application.pipeline_linkedin_points,
        "pipeline_total": application.pipeline_total,
        "pipeline_max": application.pipeline_max,
        "resume_detail": application.resume_detail,
        "github_detail": application.github_detail,
        "linkedin_detail": application.linkedin_detail,
        "assessment_score": application.assessment_score,
        "assessment_submitted_at": application.assessment_submitted_at,
        "assessment": assessment_with_answers,
    }


@router.get("/{user_id}/applications")
def list_hr_applications(user_id: int, db: Session = Depends(get_db)):
    get_active_hr_user(db, user_id)

    applications = (
        db.query(ApplicationReceived, JobListing)
        .join(JobListing, ApplicationReceived.job_id == JobListing.id)
        .filter(
            JobListing.hr_user_id == user_id,
            JobListing.is_deleted.is_(False),
            ApplicationReceived.is_deleted.is_(False),
        )
        .order_by(ApplicationReceived.created_at.desc())
        .all()
    )

    return [
        {
            "application_id": application.id,
            "full_name": application.full_name,
            "email": application.email,
            "phone": application.phone,
            "resume_key": application.resume_file_name,
            "github_url": application.github_url,
            "linkedin_url": application.linkedin_url,
            "status": application.status,
            "job": {
                "id": job.id,
                "title": job.title,
                "department": job.department,
            },
            "submitted_at": application.created_at,
            "screening_passed": application.screening_passed,
            "pipeline_total": application.pipeline_total,
            "pipeline_max": application.pipeline_max,
            "assessment_sent_at": application.assessment_sent_at,
            "assessment_score": application.assessment_score,
            "assessment_submitted_at": application.assessment_submitted_at,
        }
        for application, job in applications
    ]
