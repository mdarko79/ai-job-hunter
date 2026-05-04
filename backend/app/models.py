from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String, default="")
    work_mode: Mapped[str] = mapped_column(String, default="remote")
    days_in_office: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String, default="£")
    contract_type: Mapped[str] = mapped_column(String, default="permanent")
    rate_suffix: Mapped[str | None] = mapped_column(String, nullable=True)
    match_score: Mapped[int] = mapped_column(Integer, default=0)
    strong_matches: Mapped[list] = mapped_column(JSON, default=list)
    weak_points: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(String, default="review")
    status: Mapped[str] = mapped_column(String, default="new", index=True)
    mode: Mapped[str] = mapped_column(String, default="manual")
    source: Mapped[str] = mapped_column(String, default="")
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Multi-dimensional scoring (career-ops style A-F across 10 dimensions).
    # None means not yet scored. Stored as {dimension: "A"|"B"|"C"|"D"|"E"|"F"}
    dimensions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall_grade: Mapped[str | None] = mapped_column(String, nullable=True)


class ApplicationORM(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    company: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    mode: Mapped[str] = mapped_column(String, default="manual")
    status: Mapped[str] = mapped_column(String, default="submitted")
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Path to ATS-optimized PDF if generated
    ats_pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)


class StoryORM(Base):
    """Story Bank — STAR+R behavioural stories accumulated across applications."""
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    theme: Mapped[str] = mapped_column(String, index=True)  # leadership / conflict / failure / impact / ambiguity
    situation: Mapped[str] = mapped_column(Text)
    task: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    reflection: Mapped[str] = mapped_column(Text, default="")  # the +R
    source_application_id: Mapped[str | None] = mapped_column(String, nullable=True)
    answers_questions: Mapped[list] = mapped_column(JSON, default=list)
    is_master: Mapped[bool] = mapped_column(Boolean, default=False)  # promoted to master story
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SettingsORM(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    user_prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    auto_apply_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LogORM(Base):
    __tablename__ = "logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String, default="info")
    source: Mapped[str] = mapped_column(String, default="")
    message: Mapped[str] = mapped_column(Text, default="")
