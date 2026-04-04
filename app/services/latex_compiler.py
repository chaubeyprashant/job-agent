"""
LaTeX-to-PDF compilation service using Docker.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# "pdflatex" | "docker" | "auto" — auto prefers native pdflatex when on PATH (correct for Render).
_LATEX_BACKEND = (os.environ.get("APP_LATEX_BACKEND") or "auto").strip().lower()


class LatexCompilerService:
    """Compile LaTeX to PDF: Docker on dev machines, native ``pdflatex`` in production."""

    def __init__(self):
        self.settings = get_settings()
        self.image = "noahwu/minimal-latex:latest"  # Verified ARM64-native minimal image

    async def compile_to_pdf(self, latex_content: str) -> bytes:
        """
        Compile LaTeX string to PDF bytes.

        Uses ``pdflatex`` when on PATH (production Docker image), otherwise ``docker run``
        when the Docker CLI exists (typical local dev). Override with ``APP_LATEX_BACKEND``.
        """
        workspace_base = self.settings.data_dir / "tmp"
        workspace_base.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=workspace_base) as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            tex_file = tmp_dir / "resume.tex"
            pdf_file = tmp_dir / "resume.pdf"

            tex_file.write_text(latex_content, encoding="utf-8")
            abs_tmp_dir = tmp_dir.resolve()

            return await self._compile_with_backend(tmp_dir, abs_tmp_dir, pdf_file)

    async def _compile_with_docker(self, abs_tmp_dir: Path, pdf_file: Path) -> bytes:
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{abs_tmp_dir}:/data",
            "-w",
            "/data",
            self.image,
            "pdflatex",
            "-interaction=nonstopmode",
            "resume.tex",
        ]
        logger.info("Compiling LaTeX to PDF via Docker: %s", " ".join(docker_cmd))
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Cannot run docker for LaTeX: {e}. "
                "Install Docker, or set APP_LATEX_BACKEND=pdflatex and install TeX Live."
            ) from e
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            logger.error("LaTeX compilation failed: %s", error_msg)
            raise RuntimeError(f"LaTeX compilation failed: {error_msg}")
        if not pdf_file.exists():
            logger.error("pdflatex finished but resume.pdf was not found.")
            raise RuntimeError("PDF file was not generated.")
        return pdf_file.read_bytes()

    async def _compile_with_backend(
        self, tmp_dir: Path, abs_tmp_dir: Path, pdf_file: Path
    ) -> bytes:
        pdflatex_bin = shutil.which("pdflatex")
        docker_bin = shutil.which("docker")

        use_pdf = False
        use_docker = False
        if _LATEX_BACKEND == "pdflatex":
            use_pdf = bool(pdflatex_bin)
        elif _LATEX_BACKEND == "docker":
            use_docker = bool(docker_bin)
        else:
            # Prefer pdflatex first so production (TeX in image) never depends on docker.
            if pdflatex_bin:
                use_pdf = True
            elif docker_bin:
                use_docker = True

        if use_pdf and pdflatex_bin:
            return await self._compile_with_pdflatex(tmp_dir, pdf_file, pdflatex_bin)
        if use_docker and docker_bin:
            return await self._compile_with_docker(abs_tmp_dir, pdf_file)

        hint = (
            "Set APP_LATEX_BACKEND=pdflatex and install TeX Live (see Dockerfile), "
            "or install Docker for local dev."
        )
        raise RuntimeError(
            "LaTeX compiler not available: need `pdflatex` or `docker` on PATH. " + hint
        )

    async def _compile_with_pdflatex(
        self, tmp_dir: Path, pdf_file: Path, pdflatex: str
    ) -> bytes:
        tex_name = "resume.tex"
        logger.info("Compiling LaTeX to PDF via pdflatex: %s cwd=%s", pdflatex, tmp_dir)
        try:
            process = await asyncio.create_subprocess_exec(
                pdflatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                tex_name,
                cwd=str(tmp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Cannot run pdflatex at {pdflatex!r}: {e}. "
                "If you deploy on Render, rebuild with the repo Dockerfile (includes TeX)."
            ) from e
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            logger.error("LaTeX compilation failed: %s", error_msg)
            raise RuntimeError(f"LaTeX compilation failed: {error_msg}")
        if not pdf_file.exists():
            logger.error("pdflatex finished but resume.pdf was not found.")
            raise RuntimeError("PDF file was not generated.")
        return pdf_file.read_bytes()

compiler_service = LatexCompilerService()
