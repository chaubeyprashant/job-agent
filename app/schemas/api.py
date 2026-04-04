"""HTTP request and response bodies for FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.job import JobParseResult



class ParseJobRequest(BaseModel):
    """Raw job description text."""

    description: str = Field(min_length=1, description="Full job posting text")


class ParseJobResponse(BaseModel):
    """Parsed job structure."""

    job: JobParseResult


class TailorResumeRequest(BaseModel):
    """Base resume plus job context (pre-parsed or raw description)."""

    base_latex: str
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

    tailored_latex: str
    match_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="If job was known"
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


class RenderLatexRequest(BaseModel):
    """Compile LaTeX to PDF."""

    latex: str = Field(min_length=1, description="Full LaTeX source code")
