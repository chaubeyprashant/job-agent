"""FastAPI dependencies: services, DB session, and authenticated user."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import User, async_session_factory
from app.security.auth import decode_token
from app.services.job_parser import JobParserService
from app.services.matching_service import MatchingService
from app.services.pdf_service import PdfService
from app.services.resume_service import ResumeService

security = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async SQLAlchemy session."""
    async with async_session_factory() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Load the user from a valid Bearer JWT."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(credentials.credentials)
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    user = await session.get(User, uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_job_parser() -> JobParserService:
    return JobParserService()


def get_resume_service() -> ResumeService:
    return ResumeService()


def get_matching_service() -> MatchingService:
    return MatchingService()


def get_pdf_service() -> PdfService:
    return PdfService()


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
JobParserDep = Annotated[JobParserService, Depends(get_job_parser)]
ResumeServiceDep = Annotated[ResumeService, Depends(get_resume_service)]
MatchingServiceDep = Annotated[MatchingService, Depends(get_matching_service)]
PdfServiceDep = Annotated[PdfService, Depends(get_pdf_service)]
