"""REST API routes for parsing, tailoring, PDF generation, and apply automation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import __version__
from app.api.deps import (
    DbSession,
    JobParserDep,
    MatchingServiceDep,
    PdfServiceDep,
    ResumeServiceDep,
)
from app.automation.linkedin import apply_to_job
from app.config import get_settings
from app.models.database import ApplicationLog
from app.schemas.api import (
    ApplyRequest,
    ApplyResponse,
    GeneratePdfRequest,
    GeneratePdfResponse,
    HealthResponse,
    ParseJobRequest,
    ParseJobResponse,
    TailorResumeRequest,
    TailorResumeResponse,
)
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
    matching: MatchingServiceDep,
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

    tailored = await resume_svc.tailor_resume(
        body.base_resume,
        job_data,
        job_description=body.job_description,
        force_heuristic=body.force_heuristic,
    )
    score = matching.calculate_score(job_data, tailored)
    return TailorResumeResponse(resume=tailored, match_score=score)


@router.post("/generate-pdf", response_model=GeneratePdfResponse)
async def generate_pdf(
    body: GeneratePdfRequest,
    pdf_svc: PdfServiceDep,
) -> GeneratePdfResponse:
    """Render resume JSON to PDF and return server path."""
    path = await pdf_svc.generate_pdf(body.resume, body.filename)
    name = path.name
    download_url = f"/api/files/{name}"
    return GeneratePdfResponse(
        pdf_path=str(path),
        filename=name,
        download_url=download_url,
    )


@router.get("/files/{filename}")
async def download_generated_pdf(filename: str) -> FileResponse:
    """
    Download a PDF from the configured output directory (basename only, ``.pdf``).
    """
    settings = get_settings()
    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    candidate = (settings.output_dir / safe_name).resolve()
    root = settings.output_dir.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="File not found.") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path=candidate,
        filename=safe_name,
        media_type="application/pdf",
    )


@router.post("/apply", response_model=ApplyResponse)
async def apply(
    body: ApplyRequest,
    session: DbSession,
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

    log = ApplicationLog(
        job_url=body.job_url,
        resume_path=str(resume_fs),
        success=bool(result.get("success")),
        message=str(result.get("message", "")),
    )
    session.add(log)
    await session.commit()

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
        "database_url_scheme": s.database_url.split(":")[0],
        "gemini_configured": bool((s.gemini_api_key or "").strip()),
        "gemini_model": s.gemini_model,
    }
