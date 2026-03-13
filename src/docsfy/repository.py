from __future__ import annotations

import re
import subprocess
from pathlib import Path

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)

_CLONE_TIMEOUT = 300
_FETCH_TIMEOUT = 120
_DIFF_TIMEOUT = 60
_NAMES_TIMEOUT = 30
_CAT_FILE_TIMEOUT = 10


def extract_repo_name(repo_url: str) -> str:
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if ":" in name:
        name = name.split(":")[-1].split("/")[-1]
    return name


def clone_repo(
    repo_url: str, base_dir: Path, branch: str | None = None
) -> tuple[Path, str, str]:
    repo_name = extract_repo_name(repo_url)
    repo_path = base_dir / repo_name
    logger.info(f"Cloning {repo_name} to {repo_path}")
    clone_cmd = ["git", "clone", "--depth", "1"]
    if branch:
        clone_cmd += ["--branch", branch]
    clone_cmd += ["--", repo_url, str(repo_path)]
    try:
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            timeout=_CLONE_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        msg = f"Clone failed: {exc}"
        raise RuntimeError(msg) from exc
    if result.returncode != 0:
        msg = f"Clone failed: {result.stderr or result.stdout}"
        raise RuntimeError(msg)
    try:
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_CAT_FILE_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        msg = f"Clone failed: {exc}"
        raise RuntimeError(msg) from exc
    if sha_result.returncode != 0:
        msg = f"Failed to get commit SHA: {sha_result.stderr or sha_result.stdout}"
        raise RuntimeError(msg)
    commit_sha = sha_result.stdout.strip()
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_CAT_FILE_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        msg = f"Clone failed: {exc}"
        raise RuntimeError(msg) from exc
    if branch_result.returncode != 0:
        msg = f"Failed to detect branch: {branch_result.stderr or branch_result.stdout}"
        raise RuntimeError(msg)
    detected_branch = branch_result.stdout.strip()
    if branch and detected_branch != branch:
        msg = f"Requested branch '{branch}' resolved to '{detected_branch}'"
        raise RuntimeError(msg)
    logger.info(
        f"Cloned {repo_name} at commit {commit_sha[:8]} on branch {detected_branch}"
    )
    return repo_path, commit_sha, detected_branch


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

    # Get diff content
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--stat", "--patch", old_sha, new_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_DIFF_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"Failed to get diff: {exc}")
        return None
    if diff_result.returncode != 0:
        logger.warning(f"Failed to get diff: {diff_result.stderr}")
        return None

    # Get file list reliably using NUL-delimited output
    try:
        names_result = subprocess.run(
            ["git", "diff", "--name-only", "-z", old_sha, new_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_NAMES_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"Failed to get changed file names: {exc}")
        return None
    if names_result.returncode != 0:
        logger.warning(f"Failed to get changed file names: {names_result.stderr}")
        return None

    changed_files = [f for f in names_result.stdout.split("\0") if f]
    return changed_files, diff_result.stdout


def deepen_clone_for_diff(repo_path: Path, old_sha: str) -> bool:
    """Fetch enough history to make old_sha available for diffing.

    When a repo is cloned with ``--depth 1`` only the latest commit is
    present.  If the caller needs to diff against a previous commit we
    must fetch it first.

    Returns True if *old_sha* is now available, False on failure.
    """
    if not re.match(r"^[0-9a-fA-F]{4,64}$", old_sha):
        logger.warning("Invalid SHA format")
        return False
    try:
        # Fast-path: commit already reachable (e.g. full clone or
        # previously deepened).
        check = subprocess.run(
            ["git", "cat-file", "-t", old_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_CAT_FILE_TIMEOUT,
        )
        if check.returncode == 0:
            return True

        # Fetch the specific commit into the shallow clone.
        result = subprocess.run(
            ["git", "fetch", "--depth=1", "origin", old_sha],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_FETCH_TIMEOUT,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"Failed to deepen clone for diff: {exc}")
        return False


def get_local_repo_info(
    repo_path: Path, expected_branch: str | None = None
) -> tuple[Path, str, str]:
    """Get commit SHA and branch from a local git repository."""
    try:
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_CAT_FILE_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        msg = f"Failed to get commit SHA: {exc}"
        raise RuntimeError(msg) from exc
    if sha_result.returncode != 0:
        msg = f"Failed to get commit SHA: {sha_result.stderr or sha_result.stdout}"
        raise RuntimeError(msg)
    commit_sha = sha_result.stdout.strip()
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_CAT_FILE_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        msg = f"Failed to detect branch: {exc}"
        raise RuntimeError(msg) from exc
    if branch_result.returncode != 0:
        msg = f"Failed to detect branch: {branch_result.stderr or branch_result.stdout}"
        raise RuntimeError(msg)
    detected_branch = branch_result.stdout.strip()
    if expected_branch and detected_branch != expected_branch:
        msg = f"Branch '{detected_branch}' does not match expected '{expected_branch}'"
        raise RuntimeError(msg)
    logger.info(
        f"Local repo {repo_path.name} at commit {commit_sha[:8]} on branch {detected_branch}"
    )
    return repo_path, commit_sha, detected_branch
