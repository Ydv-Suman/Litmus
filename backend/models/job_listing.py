from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, func

from database import Base


class JobListing(Base):
    __tablename__ = "job_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    required_skills = Column(JSON, nullable=False)
    experience_level = Column(String(50), nullable=False)
    department = Column(String(100), nullable=False)
    location = Column(String(255), nullable=True)
    job_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
