from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

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
