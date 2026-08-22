"""Build only the canonical Word resume and its PDF export."""

from __future__ import annotations

import argparse
import json

from project_paths import (
    DETAILS_CONTENT_PATH,
    RESUME_DOCX_OUTPUT_PATH,
    RESUME_OUTPUT_PATH,
    SITE_CONTENT_PATH,
)
from resume.build import build_resume


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the editable Word resume from content/site.json")
    parser.add_argument("--validate-only", action="store_true", help="Validate the editable document and content without writing artifacts")
    parser.add_argument("--docx-only", action="store_true", help="Write resume.docx but skip PDF conversion")
    args = parser.parse_args()

    site_data = json.loads(SITE_CONTENT_PATH.read_text(encoding="utf-8"))
    details_data = json.loads(DETAILS_CONTENT_PATH.read_text(encoding="utf-8")) if DETAILS_CONTENT_PATH.exists() else None
    result = build_resume(
        site_data,
        details_data=details_data,
        docx_path=RESUME_DOCX_OUTPUT_PATH,
        pdf_path=None if args.docx_only or args.validate_only else RESUME_OUTPUT_PATH,
        validate_only=args.validate_only,
    )

    if args.validate_only:
        print(f"Validated {len(result.record.values)} Word Content Control mappings")
    elif args.docx_only:
        print(f"Built {RESUME_DOCX_OUTPUT_PATH.relative_to(SITE_CONTENT_PATH.parent.parent)}")
    else:
        print(
            f"Built {RESUME_DOCX_OUTPUT_PATH.relative_to(SITE_CONTENT_PATH.parent.parent)} and "
            f"{RESUME_OUTPUT_PATH.relative_to(SITE_CONTENT_PATH.parent.parent)} via {result.pdf_backend}"
        )


if __name__ == "__main__":
    main()
