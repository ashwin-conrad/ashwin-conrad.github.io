"""Convert HEIC images to JPEG files without removing the source images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps


def convert_image(source: Path, overwrite: bool) -> Path | None:
    destination = source.with_suffix(".jpg")
    if destination.exists() and not overwrite:
        print(f"Skipped: {destination} already exists")
        return None

    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.save(destination, "JPEG", quality=95, optimize=True)

    print(f"Converted: {source} -> {destination}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("assets"),
        help="Directory to search recursively (default: assets)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace JPEG files that already exist",
    )
    args = parser.parse_args()

    sources = sorted(
        path for path in args.directory.rglob("*") if path.is_file() and path.suffix.lower() == ".heic"
    )
    if not sources:
        print(f"No HEIC files found in {args.directory}")
        return

    for source in sources:
        convert_image(source, args.overwrite)


if __name__ == "__main__":
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError as error:
        raise SystemExit("HEIC support requires pillow-heif. Install it with: python -m pip install pillow-heif") from error

    main()