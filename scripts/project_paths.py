"""Shared paths for the portfolio build and editing tools."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
ASSETS_DIR = ROOT / "assets"
ASSET_RECORD_PATH = ASSETS_DIR / "asset-record.json"

SITE_CONTENT_PATH = CONTENT_DIR / "site.json"
DETAILS_CONTENT_PATH = CONTENT_DIR / "details.json"
DETAILS_DIR = CONTENT_DIR / "details"
FACTS_CONTENT_PATH = DETAILS_DIR / "facts.json"
DETAILS_WEBSITE_DIR = DETAILS_DIR / "website"
RESUME_CONTENT_PATH = CONTENT_DIR / "resume.json"
RESUME_DIR = CONTENT_DIR
DESIGN_TOKENS_PATH = DETAILS_DIR / "design-tokens.json"
SITE_OUTPUT_PATH = ROOT / "index.html"
STYLES_OUTPUT_PATH = ROOT / "styles.css"
SCRIPT_OUTPUT_PATH = ROOT / "script.js"
# The public Word resume is also the retained editable layout artifact. It
# contains the Content Controls used by the build and Word-to-JSON sync tools.
RESUME_WORKING_DOCX_PATH = ROOT / "portfolio" / "resume-working.docx"
RESUME_DOCX_OUTPUT_PATH = ROOT / "portfolio" / "resume.docx"
RESUME_OUTPUT_PATH = ROOT / "portfolio" / "resume.pdf"
