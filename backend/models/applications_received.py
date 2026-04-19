from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from database import Base


class ApplicationReceived(Base):
    __tablename__ = "applications_received"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    resume_file_name = Column(String(255), nullable=False)
    github_url = Column(String(255), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="submitted", server_default="submitted")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
    job_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False, index=True)

    pipeline_resume_points = Column(Float, nullable=True)
    pipeline_resume_max = Column(Float, nullable=True)
    pipeline_github_points = Column(Float, nullable=True)
    pipeline_github_max = Column(Float, nullable=True)
    pipeline_linkedin_points = Column(Float, nullable=True)
    pipeline_linkedin_max = Column(Float, nullable=True)
    pipeline_total = Column(Float, nullable=True)
    pipeline_max = Column(Float, nullable=True)
    screening_passed = Column(Boolean, nullable=True)
    assessment_token = Column(String(96), nullable=True, unique=True, index=True)
    assessment_payload = Column(JSON, nullable=True)
    submission_response_payload = Column(JSON, nullable=True)
    assessment_candidate_answers = Column(JSON, nullable=True)
    assessment_run_result = Column(JSON, nullable=True)
    assessment_mcq_score = Column(Float, nullable=True)
    assessment_mcq_max = Column(Float, nullable=True)
    assessment_coding_score = Column(Float, nullable=True)
    assessment_coding_max = Column(Float, nullable=True)
    assessment_total_score = Column(Float, nullable=True)
    assessment_total_max = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    final_score_max = Column(Float, nullable=True)
    assessment_submitted_at = Column(DateTime(timezone=True), nullable=True)
    assessment_sent_at = Column(DateTime(timezone=True), nullable=True)
    assessment_score = Column(Float, nullable=True)
    assessment_answers = Column(JSON, nullable=True)
    resume_detail = Column(JSON, nullable=True)
    github_detail = Column(JSON, nullable=True)
    linkedin_detail = Column(JSON, nullable=True)

    job_listing = relationship("JobListing", back_populates="applications")
