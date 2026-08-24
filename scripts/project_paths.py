"""Shared paths for the portfolio build and editing tools."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
WORKING_CONTENT_DIR = CONTENT_DIR / "working"
ASSETS_DIR = CONTENT_DIR / "assets"
ASSET_RECORD_PATH = ASSETS_DIR / "asset-record.json"

SITE_CONTENT_PATH = CONTENT_DIR / "site.json"
DETAILS_DIR = CONTENT_DIR / "details"
FACTS_CONTENT_PATH = DETAILS_DIR / "facts.json"
DETAILS_WEBSITE_DIR = DETAILS_DIR / "website"
RESUME_CONTENT_PATH = CONTENT_DIR / "resume.json"
RESUME_DIR = CONTENT_DIR
DESIGN_TOKENS_PATH = CONTENT_DIR / "styles.json"
SITE_OUTPUT_PATH = ROOT / "index.html"
STYLES_OUTPUT_PATH = ROOT / "styles.css"
SCRIPT_OUTPUT_PATH = ROOT / "script.js"
# Working Word projections live with the structured content they edit. They
# contain the Content Controls used by the Word-to-JSON sync tools, while the
# public resume artifacts remain under portfolio/.
RESUME_WORKING_DOCX_PATH = WORKING_CONTENT_DIR / "resume-working.docx"
WEBSITE_WORKING_DOCX_PATH = WORKING_CONTENT_DIR / "website-working.docx"
RESUME_DOCX_OUTPUT_PATH = ROOT / "portfolio" / "resume.docx"
RESUME_OUTPUT_PATH = ROOT / "portfolio" / "resume.pdf"
