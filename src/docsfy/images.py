"""Image support for documentation generation.

Discovers images in the ``docsfy-images/`` directory, describes them via AI
or a YAML manifest, and produces an image catalog for inclusion in generated docs.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from simple_logger.logger import get_logger

from docsfy.ai_client import AIResult, call_ai_once
from docsfy.cost_tracker import add_cost
from docsfy.json_parser import parse_json_array_response
from docsfy.prompts import SIDECAR_TOOLS

logger = get_logger(name=__name__)

DOCSFY_IMAGES_DIR = "docsfy-images"

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"})


@dataclass(frozen=True, slots=True)
class ImageEntry:
    """A single image with its filename and human-readable description."""

    filename: str
    description: str


def _humanize_filename(filename: str) -> str:
    """Convert an image filename into a human-readable label.

    ``architecture-diagram.png`` → ``"Architecture diagram"``
    """
    stem = Path(filename).stem
    label = stem.replace("-", " ").replace("_", " ")
    return label.capitalize()


def _is_safe_image_filename(filename: str) -> bool:
    """Return False if *filename* contains path-traversal or hidden-file patterns."""
    return (
        ".." not in filename
        and "/" not in filename
        and "\\" not in filename
        and not filename.startswith(".")
    )


async def _describe_images_with_ai(
    image_files: list[str],
    repo_path: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None,
) -> dict[str, str]:
    """Ask the AI to describe each image in one sentence.

    Returns a mapping of ``filename → description``.  On any failure the
    caller receives an empty dict so it can fall back to humanised filenames.
    """
    numbered = "\n".join(
        f"{idx}. {DOCSFY_IMAGES_DIR}/{f}" for idx, f in enumerate(image_files, 1)
    )

    example_output = ", ".join(
        f'{{"filename": "{f}", "description": "..."}}' for f in image_files
    )

    prompt = (
        "Read each image listed below and provide a one-sentence description of what it shows.\n"
        "Output ONLY a JSON array. No markdown fences, no explanation.\n\n"
        f"Images:\n{numbered}\n\n"
        f"Output format:\n[{example_output}]"
    )

    logger.debug("Calling AI to describe %d images", len(image_files))
    try:
        result: AIResult = await call_ai_once(
            prompt,
            ai_provider=ai_provider,
            ai_model=ai_model,
            cwd=str(repo_path),
            ai_call_timeout=ai_cli_timeout,
            tools=list(SIDECAR_TOOLS),
        )
        add_cost(result.usage.cost_usd if result.usage else None)

        if not result.success:
            logger.warning("AI image description call failed: %s", result.text[:200])
            return {}

        parsed = parse_json_array_response(result.text)
        if parsed is None:
            logger.warning("Failed to parse AI image descriptions as JSON array")
            return {}

        descriptions: dict[str, str] = {}
        for item in parsed:
            if isinstance(item, dict):
                fname = item.get("filename")
                desc = item.get("description")
                if isinstance(fname, str) and isinstance(desc, str):
                    descriptions[fname] = desc

        return descriptions

    except Exception:
        logger.exception("Unexpected error while describing images with AI")
        return {}


async def build_image_catalog(
    repo_path: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    vision_provider: str | None = None,
    vision_model: str | None = None,
) -> list[ImageEntry] | None:
    """Build an image catalog from the ``docsfy-images/`` directory.

    Returns ``None`` when the directory does not exist or contains no images.
    """
    images_dir = repo_path / DOCSFY_IMAGES_DIR
    logger.debug("Checking for docsfy-images/ at %s", images_dir)
    if not images_dir.is_dir():
        logger.debug("No docsfy-images/ directory found at %s", images_dir)
        return None

    # Collect image files (case-insensitive extension check)
    image_files: list[str] = sorted(
        f.name
        for f in images_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not image_files:
        logger.debug("No image files found in %s", images_dir)
        return None

    logger.info("Found %d image files in %s", len(image_files), images_dir)

    # Validate filenames
    safe_files: list[str] = []
    for fname in image_files:
        if _is_safe_image_filename(fname):
            safe_files.append(fname)
        else:
            logger.warning("Skipping unsafe image filename: %s", fname)

    if not safe_files:
        return None

    # Check for YAML manifest
    manifest_path = images_dir / "images.yaml"
    if manifest_path.is_file():
        import yaml

        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", manifest_path)
            return None

        if not isinstance(raw, list):
            logger.warning(
                "images.yaml must be a YAML list, got %s", type(raw).__name__
            )
            return None

        catalog: list[ImageEntry] = []
        for entry in raw:
            if not isinstance(entry, dict):
                logger.warning("Skipping non-dict entry in images.yaml: %s", entry)
                continue
            _fname = entry.get("file")
            _desc = entry.get("description")
            if not isinstance(_fname, str) or not isinstance(_desc, str):
                logger.warning(
                    "Skipping images.yaml entry with missing file/description: %s",
                    entry,
                )
                continue
            if not _is_safe_image_filename(_fname):
                logger.warning("Skipping unsafe filename in images.yaml: %s", _fname)
                continue
            if not (images_dir / _fname).is_file():
                logger.warning(
                    "Image referenced in manifest does not exist: %s", _fname
                )
                continue
            catalog.append(ImageEntry(filename=_fname, description=_desc))

        logger.info("Using images.yaml manifest with %d entries", len(catalog))
        return catalog

    # No manifest — use AI descriptions
    effective_provider = vision_provider or ai_provider
    effective_model = vision_model or ai_model

    logger.info(
        "Describing %d images with AI vision (%s/%s)",
        len(safe_files),
        effective_provider,
        effective_model,
    )
    ai_descriptions = await _describe_images_with_ai(
        image_files=safe_files,
        repo_path=repo_path,
        ai_provider=effective_provider,
        ai_model=effective_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    logger.debug("AI described %d/%d images", len(ai_descriptions), len(safe_files))

    catalog = []
    for fname in safe_files:
        desc = ai_descriptions.get(fname, _humanize_filename(fname))
        catalog.append(ImageEntry(filename=fname, description=desc))

    return catalog


def write_image_catalog(catalog: list[ImageEntry], dest_dir: Path) -> Path:
    """Write the image catalog to ``dest_dir/image_catalog.txt``.

    Each line has the format ``filename — description``.
    Returns the path to the written file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = dest_dir / "image_catalog.txt"
    lines = [f"{entry.filename} — {entry.description}" for entry in catalog]
    catalog_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.debug(
        "Wrote image catalog with %d entries to %s", len(catalog), catalog_path
    )
    return catalog_path


def copy_images_to_site(repo_path: Path, output_dir: Path) -> None:
    """Copy image files from ``docsfy-images/`` to the site output directory."""
    source_dir = repo_path / DOCSFY_IMAGES_DIR
    if not source_dir.is_dir():
        logger.debug("No docsfy-images/ directory at %s, skipping copy", source_dir)
        return

    dest_dir = output_dir / "images"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for f in source_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if not _is_safe_image_filename(f.name):
            logger.warning("Skipping unsafe image filename during copy: %s", f.name)
            continue
        shutil.copy2(f, dest_dir / f.name)
        copied += 1

    logger.info("Copied %d images to %s", copied, dest_dir)
