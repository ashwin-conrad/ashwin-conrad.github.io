"""Build the populated Word resume and its public PDF companion."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any

from .mapper import ResumeRecord, build_resume_record
from .validation import (
    validate_pdf_page_count,
    validate_record,
    validate_resume_document,
)
from .word_renderer import render_word_template


class PdfConversionUnavailableError(RuntimeError):
    """Raised after the DOCX exists but no local PDF converter is available."""


@dataclass(frozen=True)
class ResumeBuildResult:
    """Artifacts and validation information from a resume build."""

    record: ResumeRecord
    docx_path: Path | None
    pdf_path: Path | None
    pdf_backend: str | None


def build_resume(
    site_data: dict[str, Any],
    *,
    docx_path: Path,
    pdf_path: Path | None,
    details_data: dict[str, Any] | None = None,
    validate_only: bool = False,
) -> ResumeBuildResult:
    """Validate, refresh, and optionally convert the editable Word resume.

    Validation completes before any generated artifact is changed. A conversion
    failure happens only after a valid DOCX has been written, so it cannot
    corrupt the retained editable document.
    """

    validate_resume_document(docx_path)
    record = build_resume_record(site_data, details_data)
    validate_record(record)
    if validate_only:
        return ResumeBuildResult(record=record, docx_path=None, pdf_path=None, pdf_backend=None)

    # The public .docx contains the formatting and controls. Updating it
    # in-place preserves any intentional Word-only layout edits.
    render_word_template(docx_path, docx_path, record.values)
    validate_resume_document(docx_path)
    if pdf_path is None:
        return ResumeBuildResult(record=record, docx_path=docx_path, pdf_path=None, pdf_backend=None)

    backend = convert_docx_to_pdf(docx_path, pdf_path)
    validate_pdf_page_count(pdf_path)
    return ResumeBuildResult(record=record, docx_path=docx_path, pdf_path=pdf_path, pdf_backend=backend)


def convert_docx_to_pdf(input_path: Path, output_path: Path) -> str:
    """Convert with Word COM on Windows, falling back to LibreOffice headless."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    word_error: Exception | None = None
    if sys.platform == "win32":
        try:
            _convert_with_word(input_path, output_path)
            return "Microsoft Word COM"
        except Exception as error:  # pragma: no cover - environment-specific fallback
            word_error = error

    soffice = _find_soffice()
    if soffice:
        try:
            _convert_with_libreoffice(input_path, output_path, soffice)
            return "LibreOffice headless"
        except Exception as error:
            if word_error is None:
                word_error = error

    detail = f" Last conversion error: {word_error}" if word_error else ""
    raise PdfConversionUnavailableError(
        "No supported local DOCX-to-PDF converter is available. Install Microsoft Word or LibreOffice, "
        "or run `python scripts/build_resume.py --docx-only`." + detail
    )


def _convert_with_word(input_path: Path, output_path: Path) -> None:
    """Export a read-only DOCX through Word without ever saving the template."""

    import win32com.client  # type: ignore[import-not-found]

    temporary_path = output_path.with_name(f"{output_path.stem}.word-tmp.pdf")
    word = win32com.client.DispatchEx("Word.Application")
    document = None
    try:
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(str(input_path.resolve()), ReadOnly=True, AddToRecentFiles=False)
        document.ExportAsFixedFormat(str(temporary_path.resolve()), 17)  # 17 = wdExportFormatPDF
        if not temporary_path.exists():
            raise RuntimeError("Word finished without creating a PDF")
        temporary_path.replace(output_path)
    finally:
        if document is not None:
            document.Close(SaveChanges=0)
        word.Quit(SaveChanges=0)


def _find_soffice() -> Path | None:
    configured = os.environ.get("LIBREOFFICE_PATH")
    candidates = [
        Path(configured) if configured else None,
        Path(shutil.which("soffice")) if shutil.which("soffice") else None,
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    return next((candidate for candidate in candidates if candidate and candidate.exists()), None)


def _convert_with_libreoffice(input_path: Path, output_path: Path, soffice: Path) -> None:
    """Use an isolated profile so local LibreOffice state cannot affect builds."""

    with TemporaryDirectory(prefix="resume-pdf-", dir=output_path.parent) as temporary_dir:
        temporary = Path(temporary_dir)
        profile = temporary / "profile"
        profile.mkdir()
        profile_uri = "file:///" + profile.resolve().as_posix()
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
        )
        converted = temporary / f"{input_path.stem}.pdf"
        if completed.returncode != 0 or not converted.exists():
            output = (completed.stdout + "\n" + completed.stderr).strip()
            raise RuntimeError(f"LibreOffice PDF conversion failed: {output or 'no PDF produced'}")
        temporary_output = output_path.with_name(f"{output_path.stem}.libreoffice-tmp.pdf")
        shutil.copy2(converted, temporary_output)
        temporary_output.replace(output_path)
