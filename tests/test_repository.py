from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_extract_repo_name_https() -> None:
    from docsfy.repository import extract_repo_name

    assert extract_repo_name("https://github.com/org/my-repo.git") == "my-repo"
    assert extract_repo_name("https://github.com/org/my-repo") == "my-repo"


def test_extract_repo_name_ssh() -> None:
    from docsfy.repository import extract_repo_name

    assert extract_repo_name("git@github.com:org/my-repo.git") == "my-repo"


def test_clone_repo_success(tmp_path: Path) -> None:
    from docsfy.repository import clone_repo

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="abc123def\n", stderr=""),
        ]
        repo_path, sha = clone_repo("https://github.com/org/repo.git", tmp_path)

    assert repo_path == tmp_path / "repo"
    assert sha == "abc123def"  # pragma: allowlist secret


def test_clone_repo_failure(tmp_path: Path) -> None:
    import pytest
    from docsfy.repository import clone_repo

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=128, stdout="", stderr="fatal: repo not found"
        )
        with pytest.raises(RuntimeError, match="Clone failed"):
            clone_repo("https://github.com/org/bad-repo.git", tmp_path)


def test_get_local_repo_info(tmp_path: Path) -> None:
    from docsfy.repository import get_local_repo_info

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="def456\n", stderr="")
        path, sha = get_local_repo_info(tmp_path)

    assert path == tmp_path
    assert sha == "def456"
