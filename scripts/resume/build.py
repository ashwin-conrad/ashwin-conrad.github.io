"""Build the populated Word resume and its public PDF companion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any

from .mapper import ResumeRecord, build_resume_record
from .theme import apply_resume_theme
from .validation import (
    ALL_RESUME_TAGS,
    validate_pdf_page_count,
    validate_record,
    validate_resume_document,
)
from .word_renderer import render_word_template


class PdfConversionUnavailableError(RuntimeError):
    """Raised after the DOCX exists but no local PDF converter is available."""


ProgressCallback = Callable[[str], None]
WORD_PDF_TIMEOUT_SECONDS = 30
LIBREOFFICE_PDF_TIMEOUT_SECONDS = 120
WORD_PDF_WORKER_PATH = Path(__file__).with_name("word_pdf_worker.py")


@dataclass(frozen=True)
class ResumeBuildResult:
    """Artifacts and validation information from a resume build."""

    record: ResumeRecord
    docx_path: Path | None
    pdf_path: Path | None
    pdf_backend: str | None


def build_resume(
    resume_data: dict[str, Any],
    *,
    template_path: Path,
    output_path: Path,
    pdf_path: Path | None,
    validate_only: bool = False,
    design_tokens: dict[str, str] | None = None,
    progress: ProgressCallback | None = None,
) -> ResumeBuildResult:
    """Validate, refresh, and optionally convert the editable Word resume.

    Validation completes before any generated artifact is changed. A conversion
    failure happens only after a valid DOCX has been written, so it cannot
    corrupt the retained editable document.
    """

    _report(progress, "Validating the working resume and content mappings...")
    validate_resume_document(template_path)
    record = build_resume_record(resume_data)
    validate_record(record)
    if validate_only:
        return ResumeBuildResult(record=record, docx_path=None, pdf_path=None, pdf_backend=None)

    # The public .docx contains the formatting and controls. Updating it
    # in-place preserves any intentional Word-only layout edits.
    _report(progress, "Generating portfolio/resume.docx...")
    removed_tags = render_word_template(
        template_path,
        output_path,
        record.values,
        remove_blank_tags={
            tag for tag, value in record.values.items() if not value and (tag.endswith("_META") or "_BULLET" in tag)
        },
    )
    if design_tokens is not None:
        apply_resume_theme(output_path, design_tokens)
    validate_resume_document(output_path, expected_tags=set(ALL_RESUME_TAGS) - set(removed_tags))
    if pdf_path is None:
        return ResumeBuildResult(record=record, docx_path=output_path, pdf_path=None, pdf_backend=None)

    backend = convert_docx_to_pdf(output_path, pdf_path, progress=progress)
    _report(progress, f"Validating portfolio/resume.pdf created via {backend}...")
    validate_pdf_page_count(pdf_path)
    return ResumeBuildResult(record=record, docx_path=output_path, pdf_path=pdf_path, pdf_backend=backend)


def convert_docx_to_pdf(
    input_path: Path, output_path: Path, *, progress: ProgressCallback | None = None
) -> str:
    """Convert with bounded backends, preferring isolated LibreOffice."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    soffice = _find_soffice()
    if soffice:
        _report(progress, "Converting the resume to PDF with isolated LibreOffice...")
        try:
            _convert_with_libreoffice(
                input_path,
                output_path,
                soffice,
                timeout=LIBREOFFICE_PDF_TIMEOUT_SECONDS,
            )
            return "LibreOffice headless"
        except Exception as error:
            errors.append(str(error))
            _report(progress, f"LibreOffice conversion failed: {error}")

    if sys.platform == "win32":
        _report(
            progress,
            f"Trying Microsoft Word PDF export with a {WORD_PDF_TIMEOUT_SECONDS}-second limit...",
        )
        try:
            _convert_with_word(input_path, output_path, timeout=WORD_PDF_TIMEOUT_SECONDS)
            return "Microsoft Word COM"
        except Exception as error:
            errors.append(str(error))
            _report(progress, f"Microsoft Word conversion failed: {error}")

    detail = " Conversion attempts: " + " | ".join(errors) if errors else ""
    raise PdfConversionUnavailableError(
        "No supported local DOCX-to-PDF converter is available. Install Microsoft Word or LibreOffice, "
        "or run `python scripts/portfolio.py build --resume-only --docx-only`." + detail
    )


def _convert_with_word(input_path: Path, output_path: Path, *, timeout: float) -> None:
    """Run Word automation out of process so a blocked export can be stopped."""

    temporary_path = output_path.with_name(f"{output_path.stem}.word-tmp.pdf")
    _remove_temporary_file(temporary_path)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(WORD_PDF_WORKER_PATH),
                str(input_path.resolve()),
                str(temporary_path.resolve()),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        _remove_temporary_file(temporary_path)
        raise RuntimeError(f"Microsoft Word PDF conversion timed out after {timeout:g} seconds") from error
    if completed.returncode != 0 or not temporary_path.exists():
        output = (completed.stdout + "\n" + completed.stderr).strip()
        _remove_temporary_file(temporary_path)
        raise RuntimeError(f"Microsoft Word PDF conversion failed: {output or 'no PDF produced'}")
    temporary_path.replace(output_path)


def _find_soffice() -> Path | None:
    configured = os.environ.get("LIBREOFFICE_PATH")
    candidates = [
        Path(configured) if configured else None,
        Path(shutil.which("soffice")) if shutil.which("soffice") else None,
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    return next((candidate for candidate in candidates if candidate and candidate.exists()), None)


def _convert_with_libreoffice(
    input_path: Path, output_path: Path, soffice: Path, *, timeout: float
) -> None:
    """Use an isolated profile so local LibreOffice state cannot affect builds."""

    with TemporaryDirectory(prefix="resume-pdf-", dir=output_path.parent) as temporary_dir:
        temporary = Path(temporary_dir)
        profile = temporary / "profile"
        profile.mkdir()
        profile_uri = "file:///" + profile.resolve().as_posix()
        try:
            completed = subprocess.run(
                [
                    str(soffice),
                    "--headless",
                    f"-env:UserInstallation={profile_uri}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temporary),
                    str(input_path.resolve()),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"LibreOffice PDF conversion timed out after {timeout:g} seconds") from error
        converted = temporary / f"{input_path.stem}.pdf"
        if completed.returncode != 0 or not converted.exists():
            output = (completed.stdout + "\n" + completed.stderr).strip()
            raise RuntimeError(f"LibreOffice PDF conversion failed: {output or 'no PDF produced'}")
        temporary_output = output_path.with_name(f"{output_path.stem}.libreoffice-tmp.pdf")
        shutil.copy2(converted, temporary_output)
        temporary_output.replace(output_path)


def _remove_temporary_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _report(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)
