"""HTTP request and response bodies for FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.job import JobParseResult
from app.schemas.resume import Resume


class ParseJobRequest(BaseModel):
    """Raw job description text."""

    description: str = Field(min_length=1, description="Full job posting text")


class ParseJobResponse(BaseModel):
    """Parsed job structure."""

    job: JobParseResult


class TailorResumeRequest(BaseModel):
    """Base resume plus job context (pre-parsed or raw description)."""

    base_resume: Resume
    job: JobParseResult | None = None
    job_description: str | None = Field(
        default=None,
        description="If ``job`` is omitted, server parses this string first.",
    )
    force_heuristic: bool = Field(
        default=False,
        description="If true, skip Gemini and use rule-based tailoring only.",
    )


class TailorResumeResponse(BaseModel):
    """Tailored resume and optional match score."""

    resume: Resume
    match_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="If job was known"
    )


class GeneratePdfRequest(BaseModel):
    """Resume payload and optional output filename."""

    resume: Resume
    filename: str | None = Field(
        default=None,
        description="PDF filename only (no path); stored under configured output dir.",
    )


class GeneratePdfResponse(BaseModel):
    """Path to generated PDF and optional browser download URL."""

    pdf_path: str
    filename: str = Field(description="Basename of the PDF in the output directory.")
    download_url: str | None = Field(
        default=None,
        description="Relative URL path to fetch the PDF (e.g. /api/files/…).",
    )


class ApplyRequest(BaseModel):
    """LinkedIn Easy Apply automation parameters."""

    job_url: str = Field(min_length=8, description="LinkedIn job posting URL")
    resume_path: str = Field(
        min_length=1,
        description="Filesystem path to PDF resume to upload",
    )
    extra_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata for logging only",
    )


class ApplyResponse(BaseModel):
    """Result of automation attempt."""

    success: bool
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Service health."""

    status: str
    version: str
