"""Authenticated user profile and stored resume."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    DbSession,
    JobParserDep,
    MatchingServiceDep,
    ResumeServiceDep,
)
from app.models.database import UserResume
from app.schemas.api import TailorResumeResponse
from app.schemas.auth import UserPublic
from app.schemas.resume import Resume
from app.schemas.user_resume import MeResumeResponse, OptimizeJobRequest, PutResumeRequest
from app.services.resume_text_import import extract_text_from_pdf_bytes, resume_from_plaintext

router = APIRouter(prefix="/me", tags=["users"])

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def _upsert_resume(session: AsyncSession, user_id: int, resume: Resume) -> None:
    """Persist resume JSON for the user."""
    payload = resume.model_dump_json()
    result = await session.execute(select(UserResume).where(UserResume.user_id == user_id))
    row = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        session.add(UserResume(user_id=user_id, resume_json=payload, updated_at=now))
    else:
        row.resume_json = payload
        row.updated_at = now
    await session.commit()


@router.get("", response_model=UserPublic)
async def read_me(user: CurrentUser) -> UserPublic:
    """Current authenticated user."""
    return UserPublic.model_validate(user)


@router.get("/resume", response_model=MeResumeResponse)
async def get_my_resume(
    user: CurrentUser,
    session: DbSession,
) -> MeResumeResponse:
    """Return the stored resume JSON (if any)."""
    result = await session.execute(select(UserResume).where(UserResume.user_id == user.id))
    row = result.scalar_one_or_none()
    if row is None:
        return MeResumeResponse(resume=None, updated_at=None)
    resume = Resume.model_validate_json(row.resume_json)
    return MeResumeResponse(resume=resume, updated_at=row.updated_at)


@router.put("/resume", response_model=MeResumeResponse)
async def put_my_resume(
    body: PutResumeRequest,
    user: CurrentUser,
    session: DbSession,
) -> MeResumeResponse:
    """Replace the signed-in user’s stored resume."""
    await _upsert_resume(session, user.id, body.resume)
    result = await session.execute(select(UserResume).where(UserResume.user_id == user.id))
    row = result.scalar_one()
    return MeResumeResponse(
        resume=body.resume,
        updated_at=row.updated_at,
    )


@router.post("/resume/upload", response_model=MeResumeResponse)
async def upload_my_resume(
    user: CurrentUser,
    session: DbSession,
    file: UploadFile = File(..., description="Resume JSON (.json) or PDF (.pdf)"),
) -> MeResumeResponse:
    """
    Upload a resume file.

    - **JSON**: validated against the app resume schema.
    - **PDF**: text is extracted and converted heuristically to structured JSON (review in UI).
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing filename.",
        )
    name_lower = file.filename.lower()
    if not (name_lower.endswith(".json") or name_lower.endswith(".pdf")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a .json or .pdf file.",
        )
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large (max 5 MB).",
        )
    try:
        if name_lower.endswith(".json"):
            data = json.loads(raw.decode("utf-8"))
            resume = Resume.model_validate(data)
        else:
            text = extract_text_from_pdf_bytes(raw)
            if not text.strip():
                raise ValueError(
                    "Could not extract text from this PDF (image-only or protected)."
                )
            resume = resume_from_plaintext(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not import resume: {exc}",
        ) from exc
    await _upsert_resume(session, user.id, resume)
    result = await session.execute(select(UserResume).where(UserResume.user_id == user.id))
    row = result.scalar_one()
    return MeResumeResponse(resume=resume, updated_at=row.updated_at)


@router.post("/optimize", response_model=TailorResumeResponse)
async def optimize_for_job(
    body: OptimizeJobRequest,
    user: CurrentUser,
    session: DbSession,
    parser: JobParserDep,
    resume_svc: ResumeServiceDep,
    matching: MatchingServiceDep,
) -> TailorResumeResponse:
    """
    Tailor the user’s **saved** resume to the given job description.

    Requires a prior resume upload via PUT ``/me/resume`` or POST ``/me/resume/upload``.
    """
    result = await session.execute(select(UserResume).where(UserResume.user_id == user.id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Save your resume first (PUT /api/me/resume or upload).",
        )
    base = Resume.model_validate_json(row.resume_json)
    job_data = parser.parse(body.job_description)
    tailored = await resume_svc.tailor_resume(
        base,
        job_data,
        job_description=body.job_description,
        force_heuristic=body.force_heuristic,
    )
    score = matching.calculate_score(job_data, tailored)
    return TailorResumeResponse(resume=tailored, match_score=score)
