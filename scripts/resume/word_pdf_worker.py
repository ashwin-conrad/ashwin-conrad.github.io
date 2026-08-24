"""Isolated Microsoft Word PDF export worker.

This process is deliberately separate from the portfolio command so the parent
can stop it if Word automation blocks on an invisible dialog or add-in.
"""

from __future__ import annotations

from pathlib import Path
import sys


def export_pdf(input_path: Path, output_path: Path) -> None:
    import win32com.client  # type: ignore[import-not-found]

    word = win32com.client.DispatchEx("Word.Application")
    document = None
    try:
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(str(input_path.resolve()), ReadOnly=True, AddToRecentFiles=False)
        document.ExportAsFixedFormat(str(output_path.resolve()), 17)  # 17 = wdExportFormatPDF
        if not output_path.exists():
            raise RuntimeError("Word finished without creating a PDF")
    finally:
        if document is not None:
            document.Close(SaveChanges=0)
        word.Quit(SaveChanges=0)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        print("usage: word_pdf_worker.py INPUT.docx OUTPUT.pdf", file=sys.stderr)
        return 2
    try:
        export_pdf(Path(arguments[0]), Path(arguments[1]))
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
