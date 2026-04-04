"""
Application configuration loaded from YAML defaults, then environment variables.

Environment variables use the ``APP_`` prefix and nested keys as ``APP_SECTION__KEY``.
Paths resolve relative to the project root when not absolute.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    """Directory containing ``config/settings.yaml`` (repo root)."""
    return Path(__file__).resolve().parent.parent


def _load_yaml_defaults(path: Path) -> dict[str, Any]:
    """Load nested dict from YAML; return empty dict if missing."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


class AppSettings(BaseSettings):
    """Runtime settings merged from YAML + environment."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    env: str = Field(default="development", description="deployment name")
    debug: bool = Field(default=False)

    app_name: str = Field(default="Job Agent API")
    log_level: str = Field(default="INFO")

    templates_dir: Path = Field(default=Path("templates"))
    data_dir: Path = Field(default=Path("data"))
    output_dir: Path = Field(default=Path("output"))



    matching_weight_skill_overlap: float = Field(default=0.4, ge=0.0, le=1.0)
    matching_weight_keyword_match: float = Field(default=0.35, ge=0.0, le=1.0)
    matching_weight_experience_relevance: float = Field(
        default=0.25, ge=0.0, le=1.0
    )

    linkedin_headless: bool = Field(default=True)
    linkedin_max_retries: int = Field(default=3, ge=1, le=20)
    linkedin_retry_delay_seconds: float = Field(default=2.0, ge=0.0)
    linkedin_navigation_timeout_ms: int = Field(default=60_000, ge=1000)
    linkedin_action_timeout_ms: int = Field(default=15_000, ge=500)

    pdf_format: str = Field(default="A4")
    pdf_print_background: bool = Field(default=True)

    job_parser_max_keywords: int = Field(default=40, ge=1, le=200)
    job_parser_max_responsibility_bullets: int = Field(default=12, ge=1, le=100)

    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000",
        description="Comma-separated browser origins allowed by CORS.",
    )



    groq_api_key: str | None = Field(
        default=None,
        description="Groq Cloud API key for resume tailoring (optional).",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model id (e.g. llama-3.3-70b-versatile).",
    )
    groq_temperature: float = Field(default=0.35, ge=0.0, le=2.0)

    @field_validator("templates_dir", "data_dir", "output_dir", mode="before")
    @classmethod
    def _resolve_paths(cls, v: Path | str) -> Path:
        p = Path(v)
        if p.is_absolute():
            return p
        root = _project_root()
        return (root / p).resolve()


def _flatten_yaml_for_settings(yaml_data: dict[str, Any]) -> dict[str, Any]:
    """Map YAML structure to flat AppSettings field names."""
    app = yaml_data.get("app") or {}
    paths = yaml_data.get("paths") or {}
    matching = yaml_data.get("matching") or {}
    li = yaml_data.get("linkedin_automation") or {}
    pdf = yaml_data.get("pdf") or {}
    jp = yaml_data.get("job_parser") or {}
    groq = yaml_data.get("groq") or {}
    return {
        "app_name": app.get("name"),
        "log_level": app.get("log_level"),
        "templates_dir": paths.get("templates_dir"),
        "data_dir": paths.get("data_dir"),
        "output_dir": paths.get("output_dir"),
        "matching_weight_skill_overlap": matching.get("weight_skill_overlap"),
        "matching_weight_keyword_match": matching.get("weight_keyword_match"),
        "matching_weight_experience_relevance": matching.get(
            "weight_experience_relevance"
        ),
        "linkedin_max_retries": li.get("max_retries"),
        "linkedin_retry_delay_seconds": li.get("retry_delay_seconds"),
        "linkedin_navigation_timeout_ms": li.get("navigation_timeout_ms"),
        "linkedin_action_timeout_ms": li.get("action_timeout_ms"),
        "pdf_format": pdf.get("format"),
        "pdf_print_background": pdf.get("print_background"),
        "job_parser_max_keywords": jp.get("max_keywords"),
        "job_parser_max_responsibility_bullets": jp.get(
            "max_responsibility_bullets"
        ),
        "groq_model": groq.get("model"),
        "groq_temperature": groq.get("temperature"),
    }


@lru_cache
def get_settings() -> AppSettings:
    """
    Cached settings singleton.

    Loads ``config/settings.yaml`` defaults, then applies environment overrides.
    """
    yaml_path = _project_root() / "config" / "settings.yaml"
    raw = _load_yaml_defaults(yaml_path)
    flat = {k: v for k, v in _flatten_yaml_for_settings(raw).items() if v is not None}

    # Common alias for GROQ_API_KEY
    if "APP_GROQ_API_KEY" not in os.environ and "GROQ_API_KEY" in os.environ:
        os.environ["APP_GROQ_API_KEY"] = os.environ["GROQ_API_KEY"]
    return AppSettings(**flat)


def clear_settings_cache() -> None:
    """Clear settings cache (e.g. for tests)."""
    get_settings.cache_clear()
