from __future__ import annotations

import json
import subprocess
from configparser import ConfigParser
from pathlib import Path

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


def detect_version(repo_path: Path) -> str | None:
    """Auto-detect project version from common sources.

    Checks in order: pyproject.toml, package.json, Cargo.toml, setup.cfg, git tags.
    Returns the first version found, or None.
    """
    # 1. pyproject.toml
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            version = data.get("project", {}).get("version")
            if version:
                return str(version)
            version = data.get("tool", {}).get("poetry", {}).get("version")
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse pyproject.toml for version")

    # 2. package.json
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            version = data.get("version")
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse package.json for version")

    # 3. Cargo.toml
    cargo_toml = repo_path / "Cargo.toml"
    if cargo_toml.exists():
        try:
            import tomllib

            data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
            version = data.get("package", {}).get("version")
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse Cargo.toml for version")

    # 4. setup.cfg
    setup_cfg = repo_path / "setup.cfg"
    if setup_cfg.exists():
        try:
            parser = ConfigParser()
            parser.read(str(setup_cfg), encoding="utf-8")
            version = parser.get("metadata", "version", fallback=None)
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse setup.cfg for version")

    # 5. Git tags
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        tag = result.stdout.strip()
        if tag:
            return tag
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        logger.debug("git describe failed or no tags available")

    return None
