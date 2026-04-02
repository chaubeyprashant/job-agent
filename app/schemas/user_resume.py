"""Authenticated user resume storage and optimize payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.resume import Resume


class PutResumeRequest(BaseModel):
    """Replace the signed-in user’s stored resume JSON."""

    resume: Resume


class MeResumeResponse(BaseModel):
    """Stored resume for the current user, if any."""

    resume: Resume | None = None
    updated_at: datetime | None = None


class OptimizeJobRequest(BaseModel):
    """Optimize the user’s saved resume against a job description."""

    job_description: str = Field(min_length=1, description="Full job posting text")
    force_heuristic: bool = Field(
        default=False,
        description="If true, skip Gemini and use rule-based tailoring only.",
    )
