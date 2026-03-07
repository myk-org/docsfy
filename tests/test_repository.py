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
    assert mock_run.call_count == 2

    # Verify clone command
    clone_call = mock_run.call_args_list[0]
    clone_cmd = clone_call.args[0]
    assert "clone" in clone_cmd
    assert "--depth" in clone_cmd
    assert "1" in clone_cmd
    assert "--" in clone_cmd
    assert "https://github.com/org/repo.git" in clone_cmd
    assert str(tmp_path / "repo") in clone_cmd

    # Verify rev-parse command
    revparse_call = mock_run.call_args_list[1]
    assert "rev-parse" in revparse_call.args[0]
    assert revparse_call.kwargs.get("cwd") == tmp_path / "repo"


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


def test_get_local_repo_info_failure(tmp_path: Path) -> None:
    import pytest
    from docsfy.repository import get_local_repo_info

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal: not a git repository"
        )
        with pytest.raises(RuntimeError, match="Failed to get commit SHA"):
            get_local_repo_info(tmp_path)


def test_get_diff_success(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    diff_output = (
        " file.py | 1 +\n"
        " 1 file changed, 1 insertion(+)\n"
        "\n"
        "diff --git a/src/main.py b/src/main.py\n"
        "index 1234567..abcdef0 100644\n"
        "--- a/src/main.py\n"
        "+++ b/src/main.py\n"
        "@@ -1 +1,2 @@\n"
        " existing\n"
        "+new line\n"
        "diff --git a/src/utils.py b/src/utils.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/src/utils.py\n"
        "+++ b/src/utils.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/README.md b/README.md\n"
        "index 3333333..4444444 100644\n"
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1 +1 @@\n"
        "-old readme\n"
        "+new readme\n"
    )

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=diff_output,
            stderr="",
        )
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is not None
    changed_files, diff_content = result
    assert changed_files == ["src/main.py", "src/utils.py", "README.md"]
    assert diff_content == diff_output
    call_args = mock_run.call_args
    cmd = call_args.args[0]
    assert "diff" in cmd
    assert "--stat" in cmd
    assert "--patch" in cmd
    assert "abc123" in cmd
    assert "def456" in cmd


def test_get_diff_with_special_filenames(tmp_path: Path) -> None:
    """Test that filenames with spaces are extracted from diff --git headers."""
    from docsfy.repository import get_diff

    diff_output = (
        "diff --git a/src/my file.py b/src/my file.py\n"
        "index 1234567..abcdef0 100644\n"
        "--- a/src/my file.py\n"
        "+++ b/src/my file.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/dir/sub dir/test.js b/dir/sub dir/test.js\n"
        "index 2222222..3333333 100644\n"
        "--- a/dir/sub dir/test.js\n"
        "+++ b/dir/sub dir/test.js\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/README.md b/README.md\n"
        "index 4444444..5555555 100644\n"
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=diff_output,
            stderr="",
        )
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is not None
    changed_files, _ = result
    assert changed_files == [
        "src/my file.py",
        "dir/sub dir/test.js",
        "README.md",
    ]


def test_get_diff_failure(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal: bad object"
        )
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is None


def test_get_diff_empty_output(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is not None
    changed_files, diff_content = result
    assert changed_files == []
    assert diff_content == ""


def test_get_diff_timeout(tmp_path: Path) -> None:
    import subprocess

    from docsfy.repository import get_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=60)
        result = get_diff(tmp_path, "abc123", "def456")
        assert result is None


def test_get_diff_invalid_sha(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    result = get_diff(tmp_path, "not-a-sha!", "def456")
    assert result is None
