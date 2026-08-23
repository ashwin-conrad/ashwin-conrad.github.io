"""Run the local, dependency-free portfolio content editor.

It deliberately exposes a small HTTP API only on 127.0.0.1. The browser UI
edits structured objects, checks revisions before saving, and uses atomic JSON
writes so it never needs a cloud CMS or a raw-JSON editing workflow.
"""

from __future__ import annotations

import argparse
import base64
from hashlib import sha256
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_model import (
    SAFE_IMAGE_NAME,
    compose_site_content,
    detail_source_paths,
    load_details_content,
    read_json,
    validate_content_model,
    write_details_content,
    write_json_atomic,
)
from project_paths import ASSETS_DIR, RESUME_CONTENT_PATH, ROOT, SITE_CONTENT_PATH
from portfolio_workflow import build_site, sync_shared_fields
from site_renderer import render_engineering_index


DOCUMENT_NAMES = ("site", "details", "resume")
ROOT_DOCUMENT_PATHS = {"site": SITE_CONTENT_PATH, "resume": RESUME_CONTENT_PATH}
MAX_REQUEST_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


def _revision(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(body).hexdigest()


def _load_documents() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    documents = {
        "site": read_json(SITE_CONTENT_PATH),
        "details": load_details_content(),
        "resume": read_json(RESUME_CONTENT_PATH),
    }
    details_revision = sha256()
    for path in detail_source_paths():
        details_revision.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        details_revision.update(path.read_bytes())
    revisions = {
        "site": _revision(documents["site"]),
        "details": details_revision.hexdigest(),
        "resume": _revision(documents["resume"]),
    }
    return documents, revisions


def _images() -> list[str]:
    directory = ASSETS_DIR / "photos"
    if not directory.exists():
        return []
    return [
        path.relative_to(ROOT).as_posix()
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != ".gitkeep"
    ]


def _validate_documents(documents: dict[str, Any]) -> list[str]:
    if set(documents) != set(DOCUMENT_NAMES):
        return ["The editor must submit site, details, and resume documents together."]
    if not all(isinstance(document, dict) for document in documents.values()):
        return ["Every content document must be a JSON object."]
    errors = validate_content_model(documents["site"], documents["details"], documents["resume"])
    required_sections = (
        "hero", "profile", "case_studies", "experience", "skills", "documentation", "leadership", "personal_builds", "contact",
    )
    portfolio = documents["details"].get("portfolio", {})
    if not isinstance(portfolio, dict):
        errors.append("details.portfolio must be an object")
    else:
        errors.extend(f"details.portfolio is missing {key!r}" for key in required_sections if key not in portfolio)
    _validate_image_fields(documents["details"], "details", errors)
    try:
        compose_site_content(documents["site"], documents["details"])
    except Exception as error:
        errors.append(str(error))
    return errors


def _validate_image_fields(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_image_fields(child, f"{location}[{index}]", errors)
        return
    if not isinstance(value, dict):
        return
    src = value.get("src")
    if isinstance(src, str):
        if src.startswith("assets/photos/") and not (ROOT / src).is_file():
            errors.append(f"{location} references missing image: {src}")
        if src and not str(value.get("alt", "")).strip():
            errors.append(f"{location} needs alt text for {src}")
        if not src and str(value.get("alt", "")).strip():
            errors.append(f"{location} has alt text but no image source")
    for key, child in value.items():
        _validate_image_fields(child, f"{location}.{key}", errors)


class ContentEditorHandler(SimpleHTTPRequestHandler):
    """Static files plus tightly scoped local content-editing endpoints."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        print("[editor] " + format % args)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/api/content":
            documents, revisions = _load_documents()
            self._json({"documents": documents, "revisions": revisions, "images": _images()})
            return
        if route == "/api/assets":
            self._json({"images": _images()})
            return
        if route == "/editor":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/editor/")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        try:
            payload = self._payload()
            if route == "/api/content":
                self._save(payload)
            elif route == "/api/preview":
                self._preview(payload)
            elif route == "/api/sync-shared":
                self._sync_shared(payload)
            elif route == "/api/build":
                self._build(payload)
            elif route == "/api/images":
                self._import_image(payload)
            else:
                self._json({"error": "Unknown editor endpoint"}, HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server boundary
            self._json({"error": f"Editor action failed: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError("Request body is missing or too large")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def _require_revisions(self, revisions: Any, *, names: tuple[str, ...] = DOCUMENT_NAMES) -> dict[str, dict[str, Any]] | None:
        if not isinstance(revisions, dict):
            raise ValueError("Missing content revisions; refresh the editor and try again")
        current, current_revisions = _load_documents()
        changed = [name for name in names if revisions.get(name) != current_revisions[name]]
        if changed:
            self._json(
                {
                    "error": "Content changed on disk. Refresh before saving so nothing is overwritten.",
                    "changed": changed,
                    "documents": current,
                    "revisions": current_revisions,
                },
                HTTPStatus.CONFLICT,
            )
            return None
        return current

    def _save(self, payload: dict[str, Any]) -> None:
        documents = payload.get("documents")
        if not isinstance(documents, dict):
            raise ValueError("Missing documents")
        if self._require_revisions(payload.get("revisions")) is None:
            return
        errors = _validate_documents(documents)
        if errors:
            self._json({"error": "Content validation failed", "errors": errors}, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        for name, path in ROOT_DOCUMENT_PATHS.items():
            write_json_atomic(path, documents[name])
        write_details_content(documents["details"])
        _, revisions = _load_documents()
        self._json({"ok": True, "revisions": revisions})

    def _preview(self, payload: dict[str, Any]) -> None:
        documents = payload.get("documents")
        if not isinstance(documents, dict):
            raise ValueError("Missing documents")
        errors = _validate_documents(documents)
        if errors:
            self._json({"error": "Preview validation failed", "errors": errors}, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        html = render_engineering_index(compose_site_content(documents["site"], documents["details"]))
        html = html.replace("<head>", '<head>\n    <base href="/">', 1)
        self._json({"html": html})

    def _sync_shared(self, payload: dict[str, Any]) -> None:
        current = self._require_revisions(payload.get("revisions"), names=("site", "resume"))
        if current is None:
            return
        updated, report = sync_shared_fields(current["site"], current["resume"], force=bool(payload.get("force")))
        errors = validate_content_model(current["site"], current["details"], updated)
        if errors:
            self._json({"error": "Shared-field result is invalid", "errors": errors}, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        write_json_atomic(RESUME_CONTENT_PATH, updated)
        _, revisions = _load_documents()
        self._json({"ok": True, "resume": updated, "revisions": revisions, "report": report})

    def _build(self, payload: dict[str, Any]) -> None:
        if self._require_revisions(payload.get("revisions")) is None:
            return
        result = build_site()
        self._json(
            {
                "ok": True,
                "output": "Built index.html, styles.css, script.js, portfolio/resume.docx, and "
                f"portfolio/resume.pdf via {result.resume.pdf_backend}",
            }
        )

    def _import_image(self, payload: dict[str, Any]) -> None:
        filename = payload.get("filename")
        encoded = payload.get("content_base64")
        if not isinstance(filename, str) or not SAFE_IMAGE_NAME.fullmatch(filename):
            raise ValueError("Use a simple image filename containing letters, numbers, dots, underscores, or hyphens")
        if Path(filename).suffix.casefold() not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("Supported image types are JPG, PNG, WebP, GIF, and SVG")
        if not isinstance(encoded, str):
            raise ValueError("Missing image data")
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("Image is empty or exceeds the 15 MB local-editor limit")
        destination = ASSETS_DIR / "photos" / filename
        if destination.exists():
            self._json({"error": f"Image already exists: assets/photos/{filename}"}, HTTPStatus.CONFLICT)
            return
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(raw)
        temporary.replace(destination)
        self._json({"ok": True, "src": destination.relative_to(ROOT).as_posix(), "images": _images()})

    def _json(self, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local portfolio content editor")
    parser.add_argument("--port", type=int, default=4173, help="Local port (default: 4173)")
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ContentEditorHandler)
    print(f"Content editor: http://127.0.0.1:{args.port}/editor/")
    print("The editor is local-only. Press Ctrl+C to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nContent editor stopped.")
    finally:
        server.server_close()
    return 0
