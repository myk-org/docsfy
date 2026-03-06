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


def test_get_changed_files_success(tmp_path: Path) -> None:
    from docsfy.repository import get_changed_files

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/main.py\0src/utils.py\0README.md\0",
            stderr="",
        )
        files = get_changed_files(tmp_path, "abc123", "def456")

    assert files == ["src/main.py", "src/utils.py", "README.md"]
    call_args = mock_run.call_args
    assert "diff" in call_args.args[0]
    assert "--name-only" in call_args.args[0]
    assert "-z" in call_args.args[0]
    assert "abc123" in call_args.args[0]
    assert "def456" in call_args.args[0]


def test_get_changed_files_with_special_names(tmp_path: Path) -> None:
    """Test that filenames with spaces and embedded newlines are parsed correctly with -z flag.

    A naive newline-based split would break on filenames that contain spaces
    (combined with the surrounding entries) or literal newlines.  The -z flag
    makes ``git diff`` use NUL as the delimiter, so the parser must split on
    ``\\0`` rather than ``\\n``.
    """
    from docsfy.repository import get_changed_files

    with patch("docsfy.repository.subprocess.run") as mock_run:
        # Simulate NUL-delimited output that includes:
        #   - a filename with a space ("src/my file.py")
        #   - a path whose directory contains a space ("dir/sub dir/test.js")
        #   - a filename with an embedded newline ("dir/file\nname.py")
        #   - a plain filename ("README.md")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/my file.py\0dir/sub dir/test.js\0dir/file\nname.py\0README.md\0",
            stderr="",
        )
        files = get_changed_files(tmp_path, "abc123", "def456")

    assert files == [
        "src/my file.py",
        "dir/sub dir/test.js",
        "dir/file\nname.py",
        "README.md",
    ]

    # Confirm -z flag is passed so git uses NUL delimiters
    call_args = mock_run.call_args
    assert "-z" in call_args.args[0]


def test_get_changed_files_failure(tmp_path: Path) -> None:
    from docsfy.repository import get_changed_files

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal: bad object"
        )
        files = get_changed_files(tmp_path, "abc123", "def456")

    assert files is None


def test_get_changed_files_empty_output(tmp_path: Path) -> None:
    from docsfy.repository import get_changed_files

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        files = get_changed_files(tmp_path, "abc123", "def456")

    assert files == []
