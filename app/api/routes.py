"""REST API routes for parsing, tailoring, and apply automation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from app import __version__
from app.api.deps import (
    JobParserDep,
    ResumeServiceDep,
)
from app.automation.linkedin import apply_to_job
from app.config import get_settings
from app.schemas.api import (
    ApplyRequest,
    ApplyResponse,
    HealthResponse,
    ParseJobRequest,
    ParseJobResponse,
    RenderLatexRequest,
    TailorResumeRequest,
    TailorResumeResponse,
)
from app.services.latex_compiler import compiler_service
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", version=__version__)


@router.post("/parse-job", response_model=ParseJobResponse)
async def parse_job(
    body: ParseJobRequest,
    parser: JobParserDep,
) -> ParseJobResponse:
    """Parse a raw job description into structured fields."""
    job = parser.parse(body.description)
    return ParseJobResponse(job=job)


@router.post("/tailor-resume", response_model=TailorResumeResponse)
async def tailor_resume(
    body: TailorResumeRequest,
    parser: JobParserDep,
    resume_svc: ResumeServiceDep,
) -> TailorResumeResponse:
    """
    Tailor a base resume to a job.

    Provide either ``job`` or ``job_description`` (the latter will be parsed first).
    """
    if body.job is not None:
        job_data = body.job
    elif body.job_description:
        job_data = parser.parse(body.job_description)
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide `job` or `job_description`.",
        )

    tailored_latex = await resume_svc.tailor_resume(
        body.base_latex,
        job_data,
        job_description=body.job_description,
        force_heuristic=body.force_heuristic,
    )
    
    return TailorResumeResponse(tailored_latex=tailored_latex, match_score=None)


@router.post("/apply", response_model=ApplyResponse)
async def apply(
    body: ApplyRequest,
) -> ApplyResponse:
    """
    Run LinkedIn Easy Apply automation (requires local Playwright browsers).

    Persists an audit row to SQLite (or your configured database URL).
    """
    resume_fs = Path(body.resume_path).expanduser()
    try:
        result = await apply_to_job(body.job_url, resume_fs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



    logger.info(
        "Apply job_url=%s success=%s",
        body.job_url,
        result.get("success"),
    )
    return ApplyResponse(
        success=bool(result.get("success")),
        message=str(result.get("message", "")),
        detail={k: v for k, v in result.items() if k not in ("success", "message")},
    )


@router.get("/config/paths")
async def config_paths() -> dict[str, str | bool]:
    """Expose resolved paths from settings (no secrets)."""
    s = get_settings()
    return {
        "templates_dir": str(s.templates_dir),
        "data_dir": str(s.data_dir),
        "output_dir": str(s.output_dir),
        "groq_configured": bool((s.groq_api_key or "").strip()),
        "groq_model": s.groq_model,
    }


@router.post("/latex-to-pdf")
async def render_pdf(body: RenderLatexRequest) -> Response:
    """Compile LaTeX to PDF and return bytes."""
    try:
        pdf_bytes = await compiler_service.compile_to_pdf(body.latex)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=resume.pdf"},
        )
    except Exception as exc:
        logger.error("Failed to render PDF: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
