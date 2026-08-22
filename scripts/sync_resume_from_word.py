"""Sync manual Word resume edits into JSON, PDF, and website artifacts."""

from __future__ import annotations

import json
import subprocess
import sys

from project_paths import RESUME_DOCX_OUTPUT_PATH, SITE_CONTENT_PATH
from resume.validation import validate_resume_document
from resume.word_renderer import read_content_control_values
from resume.word_sync import sync_word_values_into_site


def main() -> None:
    validate_resume_document(RESUME_DOCX_OUTPUT_PATH)
    values = read_content_control_values(RESUME_DOCX_OUTPUT_PATH)
    site_data = json.loads(SITE_CONTENT_PATH.read_text(encoding="utf-8"))
    updated = sync_word_values_into_site(site_data, values)
    SITE_CONTENT_PATH.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    build = subprocess.run([sys.executable, "scripts/build_site.py"], check=False)
    if build.returncode:
        raise SystemExit(build.returncode)
    print("Imported Word resume edits into content/site.json and refreshed the website and PDF.")


if __name__ == "__main__":
    main()
