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
    names_output = "src/main.py\0src/utils.py\0README.md\0"

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=diff_output, stderr=""),
            MagicMock(returncode=0, stdout=names_output, stderr=""),
        ]
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is not None
    changed_files, diff_content = result
    assert changed_files == ["src/main.py", "src/utils.py", "README.md"]
    assert diff_content == diff_output
    assert mock_run.call_count == 2

    # Verify diff --stat --patch call
    diff_cmd = mock_run.call_args_list[0].args[0]
    assert "--stat" in diff_cmd
    assert "--patch" in diff_cmd

    # Verify diff --name-only -z call
    names_cmd = mock_run.call_args_list[1].args[0]
    assert "--name-only" in names_cmd
    assert "-z" in names_cmd


def test_get_diff_with_special_filenames(tmp_path: Path) -> None:
    """Test that filenames with spaces and 'b/' in paths are handled correctly."""
    from docsfy.repository import get_diff

    diff_output = (
        "diff --git a/src/my file.py b/src/my file.py\n"
        "index 1234567..abcdef0 100644\n"
        "--- a/src/my file.py\n"
        "+++ b/src/my file.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/docs/a b/file.md b/docs/a b/file.md\n"
        "index 2222222..3333333 100644\n"
        "--- a/docs/a b/file.md\n"
        "+++ b/docs/a b/file.md\n"
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
    names_output = "src/my file.py\0docs/a b/file.md\0README.md\0"

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=diff_output, stderr=""),
            MagicMock(returncode=0, stdout=names_output, stderr=""),
        ]
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is not None
    changed_files, _ = result
    assert changed_files == [
        "src/my file.py",
        "docs/a b/file.md",
        "README.md",
    ]


def test_get_diff_deleted_file(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    diff_output = (
        "diff --git a/src/deleted.py b/src/deleted.py\n"
        "deleted file mode 100644\n"
        "index abc1234..0000000\n"
        "--- a/src/deleted.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-print('old file')\n"
    )
    names_output = "src/deleted.py\0"

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=diff_output, stderr=""),
            MagicMock(returncode=0, stdout=names_output, stderr=""),
        ]
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is not None
    changed_files, _ = result
    assert changed_files == ["src/deleted.py"]


def test_get_diff_diff_failure(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal: bad object"
        )
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is None


def test_get_diff_name_only_failure(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="some diff", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="fatal: bad object"),
        ]
        result = get_diff(tmp_path, "abc123", "def456")

    assert result is None


def test_get_diff_empty_output(tmp_path: Path) -> None:
    from docsfy.repository import get_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
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


def test_deepen_clone_for_diff_invalid_sha(tmp_path: Path) -> None:
    from docsfy.repository import deepen_clone_for_diff

    assert deepen_clone_for_diff(tmp_path, "not-a-sha!") is False


def test_deepen_clone_for_diff_already_available(tmp_path: Path) -> None:
    from docsfy.repository import deepen_clone_for_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        # cat-file succeeds -> commit already present
        mock_run.return_value = MagicMock(returncode=0, stdout="commit\n", stderr="")
        assert deepen_clone_for_diff(tmp_path, "abc123") is True

    # Only one call (cat-file), no fetch needed
    assert mock_run.call_count == 1
    cmd = mock_run.call_args.args[0]
    assert "cat-file" in cmd


def test_deepen_clone_for_diff_fetch_success(tmp_path: Path) -> None:
    from docsfy.repository import deepen_clone_for_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            # cat-file fails -> commit not present
            MagicMock(returncode=1, stdout="", stderr="fatal: bad object"),
            # fetch succeeds
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        assert deepen_clone_for_diff(tmp_path, "abc123") is True

    assert mock_run.call_count == 2
    fetch_cmd = mock_run.call_args_list[1].args[0]
    assert "fetch" in fetch_cmd
    assert "abc123" in fetch_cmd


def test_deepen_clone_for_diff_fetch_failure(tmp_path: Path) -> None:
    from docsfy.repository import deepen_clone_for_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            # cat-file fails
            MagicMock(returncode=1, stdout="", stderr=""),
            # fetch also fails
            MagicMock(returncode=128, stdout="", stderr="fatal: remote error"),
        ]
        assert deepen_clone_for_diff(tmp_path, "abc123") is False


def test_deepen_clone_for_diff_timeout(tmp_path: Path) -> None:
    import subprocess

    from docsfy.repository import deepen_clone_for_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
        assert deepen_clone_for_diff(tmp_path, "abc123") is False


def test_deepen_clone_for_diff_os_error(tmp_path: Path) -> None:
    from docsfy.repository import deepen_clone_for_diff

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = OSError("No such file or directory")
        assert deepen_clone_for_diff(tmp_path, "abc123") is False
