"""
LinkedIn Easy Apply automation via Playwright.

**Important:** LinkedIn's DOM changes frequently; selectors are best-effort.
Respect LinkedIn's Terms of Service and use only on accounts you own.
This module logs failures clearly and never swallows exceptions silently.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Common Easy Apply entry points (LinkedIn changes these; list is fallback chain)
_EASY_APPLY_SELECTORS: list[str] = [
    "button.jobs-apply-button",
    "button[aria-label*='Easy Apply']",
    "button:has-text('Easy Apply')",
    "div.jobs-apply-button--top-card button",
    "button.jobs-s-apply",
]

_RESUME_INPUT_SELECTORS: list[str] = [
    "input[type='file'][accept*='pdf']",
    "input[type='file']",
]

_NEXT_SELECTORS: list[str] = [
    "button[aria-label='Continue to next step']",
    "button:has-text('Next')",
    "button[data-control-name='continue_unify']",
    "footer button:has-text('Next')",
]

_REVIEW_SUBMIT_SELECTORS: list[str] = [
    "button[aria-label='Submit your application']",
    "button:has-text('Submit application')",
    "footer button:has-text('Submit')",
]


async def apply_to_job(job_url: str, resume_path: str | Path) -> dict[str, Any]:
    """
    Open a job URL, start Easy Apply, upload a PDF resume, advance, and submit.

    Args:
        job_url: Full LinkedIn job posting URL.
        resume_path: Path to the resume PDF on disk.

    Returns:
        Dict with ``success`` (bool), ``message`` (str), and diagnostic keys.

    Raises:
        FileNotFoundError: If ``resume_path`` does not exist.
    """
    settings = get_settings()
    path = Path(resume_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Resume file not found: {path}")

    last_error: str | None = None
    for attempt in range(1, settings.linkedin_max_retries + 1):
        logger.info(
            "LinkedIn apply attempt %s/%s url=%s",
            attempt,
            settings.linkedin_max_retries,
            job_url,
        )
        try:
            result = await _run_flow(
                job_url,
                path,
                headless=settings.linkedin_headless,
                navigation_timeout=settings.linkedin_navigation_timeout_ms,
                action_timeout=settings.linkedin_action_timeout_ms,
            )
            if result.get("success"):
                return result
            last_error = str(result.get("message", "unknown"))
        except (PlaywrightError, PlaywrightTimeout, OSError) as exc:
            last_error = repr(exc)
            logger.warning("Attempt %s failed: %s", attempt, exc)

        if attempt < settings.linkedin_max_retries:
            await asyncio.sleep(settings.linkedin_retry_delay_seconds)

    return {
        "success": False,
        "message": f"Failed after {settings.linkedin_max_retries} attempts: {last_error}",
        "job_url": job_url,
        "resume_path": str(path),
    }


async def _run_flow(
    job_url: str,
    resume_path: Path,
    *,
    headless: bool,
    navigation_timeout: int,
    action_timeout: int,
) -> dict[str, Any]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        page.set_default_timeout(action_timeout)
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=navigation_timeout)
            clicked = await _click_first_match(page, _EASY_APPLY_SELECTORS, timeout=action_timeout)
            if not clicked:
                return {
                    "success": False,
                    "message": "Easy Apply button not found — page structure may have changed or job closed.",
                    "step": "easy_apply",
                }

            await asyncio.sleep(0.8)
            uploaded = await _upload_resume(page, resume_path, action_timeout)
            if not uploaded:
                return {
                    "success": False,
                    "message": "Could not locate resume file input in the Easy Apply dialog.",
                    "step": "upload",
                }

            submitted = await _advance_to_submit(page, max_steps=25, action_timeout=action_timeout)
            if not submitted:
                return {
                    "success": False,
                    "message": "Could not reach submit step — manual review required.",
                    "step": "submit",
                }

            return {
                "success": True,
                "message": "Application flow completed (verify in LinkedIn UI).",
                "job_url": job_url,
                "resume_path": str(resume_path),
            }
        finally:
            await context.close()
            await browser.close()


async def _click_first_match(page, selectors: list[str], timeout: int) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_enabled():
                await loc.click(timeout=timeout)
                return True
        except (PlaywrightError, PlaywrightTimeout):
            continue
    return False


async def _upload_resume(page, resume_path: Path, timeout: int) -> bool:
    for sel in _RESUME_INPUT_SELECTORS:
        try:
            inp = page.locator(sel).first
            if await inp.count():
                await inp.set_input_files(str(resume_path), timeout=timeout)
                return True
        except (PlaywrightError, PlaywrightTimeout):
            continue
    return False


async def _advance_to_submit(page, max_steps: int, action_timeout: int) -> bool:
    """Click Next until Submit appears, then click Submit."""
    for _ in range(max_steps):
        for sel in _REVIEW_SUBMIT_SELECTORS:
            btn = page.locator(sel).first
            try:
                if await btn.count() and await btn.is_enabled():
                    await btn.click(timeout=action_timeout)
                    return True
            except (PlaywrightError, PlaywrightTimeout):
                pass

        progressed = await _click_first_match(page, _NEXT_SELECTORS, action_timeout)
        if not progressed:
            # Optional: short-circuit if stuck (custom questions)
            logger.warning("No Next/Submit control found; flow may need human input.")
            return False
        await asyncio.sleep(0.4)
    return False
