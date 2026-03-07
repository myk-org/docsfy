from __future__ import annotations

import re
import subprocess
from pathlib import Path

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


def extract_repo_name(repo_url: str) -> str:
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if ":" in name:
        name = name.split(":")[-1].split("/")[-1]
    return name


def clone_repo(repo_url: str, base_dir: Path) -> tuple[Path, str]:
    repo_name = extract_repo_name(repo_url)
    repo_path = base_dir / repo_name
    logger.info(f"Cloning {repo_name} to {repo_path}")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--", repo_url, str(repo_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        msg = f"Clone failed: {result.stderr or result.stdout}"
        raise RuntimeError(msg)
    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if sha_result.returncode != 0:
        msg = f"Failed to get commit SHA: {sha_result.stderr or sha_result.stdout}"
        raise RuntimeError(msg)
    commit_sha = sha_result.stdout.strip()
    logger.info(f"Cloned {repo_name} at commit {commit_sha[:8]}")
    return repo_path, commit_sha


_DIFF_FILE_RE = re.compile(r"^diff --git a/.+ b/(.+)$", re.MULTILINE)


def get_diff(
    repo_path: Path, old_sha: str, new_sha: str
) -> tuple[list[str], str] | None:
    """Get changed files and diff content between two commits.

    Returns a tuple of (changed_files, diff_content), or None on error.
    changed_files is a list of file paths that changed.
    diff_content is the full diff including stat and patch.
    """
    if not re.match(r"^[0-9a-fA-F]{4,64}$", old_sha) or not re.match(
        r"^[0-9a-fA-F]{4,64}$", new_sha
    ):
        logger.warning("Invalid SHA format")
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "--patch", old_sha, new_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"Failed to get diff: {exc}")
        return None
    if result.returncode != 0:
        logger.warning(f"Failed to get diff: {result.stderr}")
        return None

    diff_content = result.stdout
    changed_files = [m.group(1) for m in _DIFF_FILE_RE.finditer(diff_content)]
    return changed_files, diff_content


def get_local_repo_info(repo_path: Path) -> tuple[Path, str]:
    """Get commit SHA from a local git repository."""
    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if sha_result.returncode != 0:
        msg = f"Failed to get commit SHA: {sha_result.stderr or sha_result.stdout}"
        raise RuntimeError(msg)
    commit_sha = sha_result.stdout.strip()
    logger.info(f"Local repo {repo_path.name} at commit {commit_sha[:8]}")
    return repo_path, commit_sha
