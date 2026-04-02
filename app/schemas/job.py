"""Structured output from job description parsing."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobParseResult(BaseModel):
    """Normalized job posting fields used for tailoring and matching."""

    role: str = Field(description="Inferred job title or role name")
    seniority: str = Field(
        description="e.g. junior, mid, senior, lead, staff, principal"
    )
    must_have_skills: list[str] = Field(default_factory=list)
    good_to_have_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
