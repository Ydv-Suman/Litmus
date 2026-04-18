from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.hr_user import HrUser
from models.job_listing import JobListing


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


class JobListingCreateRequest(BaseModel):
    title: str
    description: str
    required_skills: list[str]
    experience_level: str
    department: str
    location: str | None = None
    job_type: str
    hr_user_id: int

    @field_validator(
        "title",
        "description",
        "experience_level",
        "department",
        "job_type",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required.")
        return cleaned

    @field_validator("required_skills")
    @classmethod
    def validate_required_skills(cls, value: list[str]) -> list[str]:
        cleaned_skills = [skill.strip() for skill in value if skill.strip()]
        if not cleaned_skills:
            raise ValueError("At least one required skill is needed.")
        return cleaned_skills

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    jobs = (
        db.query(JobListing)
        .filter(JobListing.is_active.is_(True), JobListing.is_deleted.is_(False))
        .order_by(JobListing.title.asc())
        .all()
    )

    return [
        {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "job_type": job.job_type,
            "experience_level": job.experience_level,
            "hr_user_id": job.hr_user_id,
        }
        for job in jobs
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobListingCreateRequest, db: Session = Depends(get_db)):
    hr_user = (
        db.query(HrUser)
        .filter(
            HrUser.id == payload.hr_user_id,
            HrUser.is_active.is_(True),
            HrUser.is_deleted.is_(False),
        )
        .first()
    )
    if hr_user is None:
        raise HTTPException(status_code=404, detail="Active HR user not found.")

    job = JobListing(
        title=payload.title,
        description=payload.description,
        required_skills=payload.required_skills,
        experience_level=payload.experience_level,
        department=payload.department,
        location=payload.location,
        job_type=payload.job_type,
        hr_user_id=payload.hr_user_id,
    )

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create job listing.") from exc

    return {
        "message": "Job listing created successfully.",
        "job": {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "job_type": job.job_type,
            "experience_level": job.experience_level,
            "hr_user_id": job.hr_user_id,
        },
    }
