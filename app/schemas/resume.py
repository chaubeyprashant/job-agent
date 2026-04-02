"""
Resume domain schema: basics, skills, experience, projects, education.

Supports loading from JSON files or dicts and applying partial updates while
keeping types enforced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator


class Basics(BaseModel):
    """Core identity and contact block."""

    name: str
    headline: str | None = None
    summary: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Skill buckets for tailoring and display order."""

    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    """Single employment entry."""

    company: str
    title: str
    location: str | None = None
    start: str
    end: str | None = "Present"
    highlights: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    """Portfolio or side project."""

    name: str
    description: str | None = None
    tech: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    """Education entry."""

    institution: str
    degree: str
    field: str | None = None
    end: str | None = None


class Resume(BaseModel):
    """
    Full resume document.

    Use :meth:`from_json_file`, :meth:`from_json_str`, or standard construction.
    Use :meth:`apply_patch` for dynamic, shallow-merge updates of nested models.
    """

    basics: Basics
    skills: Skills
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)

    @field_validator("experience", "projects", "education", mode="before")
    @classmethod
    def _default_list(cls, v: Any) -> list:
        return v if isinstance(v, list) else []

    @classmethod
    def from_json_file(cls, path: str | Path) -> Self:
        """Load and validate resume JSON from disk."""
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        return cls.from_json_str(text)

    @classmethod
    def from_json_str(cls, raw: str) -> Self:
        """Parse JSON string into a :class:`Resume`."""
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Resume JSON must be an object")
        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build from a plain dict (e.g. API JSON)."""
        return cls.model_validate(data)

    def apply_patch(self, patch: dict[str, Any]) -> Self:
        """
        Return a new resume with shallow-merge semantics.

        Top-level keys replace nested models when provided as dicts.
        Does not invent facts—only restructures or updates provided fields.
        """
        current = self.model_dump(mode="python")
        merged = _deep_merge(current, patch)
        return Resume.model_validate(merged)

    def to_json_str(self, *, indent: int | None = 2) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=indent)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge dicts; patch wins. Lists from patch replace lists entirely."""
    out = dict(base)
    for key, val in patch.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(val, dict)
        ):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out
