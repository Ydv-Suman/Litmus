from typing import Generator

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from models.job_listing import JobListing


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


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
        }
        for job in jobs
    ]
