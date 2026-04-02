"""
Async SQLAlchemy setup: SQLite by default, PostgreSQL-compatible URL swap.

Uses ``APP_DATABASE_URL`` from settings.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


class User(Base):
    """Application user (email + password hash)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resume_row: Mapped["UserResume | None"] = relationship(
        "UserResume",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class UserResume(Base):
    """
    One canonical resume JSON blob per user (name, contact, experience, etc.).

    Used by :func:`ResumeService.tailor_resume` when optimizing for a job.
    """

    __tablename__ = "user_resumes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    resume_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="resume_row")


class ApplicationLog(Base):
    """
    Audit row for application attempts (optional persistence from API).

    Replace SQLite URL with ``postgresql+asyncpg://...`` for PostgreSQL.
    """

    __tablename__ = "application_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    resume_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    success: Mapped[bool] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def _make_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
    )


engine = _make_engine()
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
