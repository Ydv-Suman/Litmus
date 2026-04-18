import os
from typing import Generator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from models.applications_received import ApplicationReceived


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
    resume_file_name = os.path.basename(resume.filename or "").strip()
    if not resume_file_name:
        raise HTTPException(status_code=400, detail="Resume file name is required.")

    application = Application(
        full_name=full_name.strip(),
        email=email.strip().lower(),
        phone=phone.strip(),
        resume_file_name=resume_file_name,
        github_url=github_url.strip() if github_url else None,
        linkedin_url=linkedin_url.strip() if linkedin_url else None,
        job_id=job_id,
    )

    try:
        db.add(application)
        db.commit()
        db.refresh(application)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to submit application.",
        ) from exc

    return {
        "message": "Application submitted successfully.",
        "application_id": application.id,
        "status": application.status,
    }
