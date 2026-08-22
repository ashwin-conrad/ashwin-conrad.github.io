"""Shared paths for the portfolio build and editing tools."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
ASSETS_DIR = ROOT / "assets"

SITE_CONTENT_PATH = CONTENT_DIR / "site.json"
DETAILS_CONTENT_PATH = CONTENT_DIR / "details.json"
RESUME_TEMPLATE_PATH = CONTENT_DIR / "resume_template.xlsx"
SITE_OUTPUT_PATH = ROOT / "index.html"
STYLES_OUTPUT_PATH = ROOT / "styles.css"
RESUME_OUTPUT_PATH = ROOT / "portfolio" / "resume.pdf"
