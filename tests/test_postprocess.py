from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch


def test_detect_version_pyproject_toml(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "2.1.0"\n'
    )
    assert detect_version(tmp_path) == "2.1.0"


def test_detect_version_pyproject_poetry(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "myapp"\nversion = "3.0.0"\n'
    )
    assert detect_version(tmp_path) == "3.0.0"


def test_detect_version_package_json(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "package.json").write_text('{"name": "myapp", "version": "1.5.2"}')
    assert detect_version(tmp_path) == "1.5.2"


def test_detect_version_cargo_toml(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "myapp"\nversion = "0.3.1"\n'
    )
    assert detect_version(tmp_path) == "0.3.1"


def test_detect_version_setup_cfg(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "setup.cfg").write_text("[metadata]\nname = myapp\nversion = 4.0.0\n")
    assert detect_version(tmp_path) == "4.0.0"


def test_detect_version_git_tag(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="v1.0.0\n", stderr=""
        )
        assert detect_version(tmp_path) == "v1.0.0"


def test_detect_version_git_tag_fails(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        assert detect_version(tmp_path) is None


def test_detect_version_priority_order(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.0.0"\n'
    )
    (tmp_path / "package.json").write_text('{"name": "myapp", "version": "2.0.0"}')
    assert detect_version(tmp_path) == "1.0.0"


def test_detect_version_none_when_no_sources(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        assert detect_version(tmp_path) is None
