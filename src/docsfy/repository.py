from __future__ import annotations

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
    logger.info(f"Cloning {repo_url} to {repo_path}")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
        capture_output=True,
        text=True,
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
    commit_sha = sha_result.stdout.strip()
    logger.info(f"Cloned {repo_name} at commit {commit_sha[:8]}")
    return repo_path, commit_sha
