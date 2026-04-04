"""FastAPI dependencies: services, DB session, and authenticated user."""

from __future__ import annotations


from app.services.job_parser import JobParserService
from app.services.resume_service import ResumeService

from typing import Annotated
from fastapi import Depends


def get_job_parser() -> JobParserService:
    return JobParserService()


def get_resume_service() -> ResumeService:
    return ResumeService()


JobParserDep = Annotated[JobParserService, Depends(get_job_parser)]
ResumeServiceDep = Annotated[ResumeService, Depends(get_resume_service)]

