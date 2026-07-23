from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from docsfy.cli.main import app

runner = CliRunner()


def _make_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
    method: str = "GET",
    url: str = "https://example.com/api/status",
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json_data or {},
        request=httpx.Request(method, url),
    )


def _make_mock_client() -> MagicMock:
    """Create a mock DocsfyClient."""
    client = MagicMock()
    client.server_url = "https://example.com"
    client.username = "admin"
    client.password = "test-key"  # pragma: allowlist secret
    return client


@pytest.fixture
def mock_client():
    """Mock get_client to return a fake DocsfyClient."""
    client = _make_mock_client()
    with patch("docsfy.cli.main.get_client", return_value=client):
        yield client


@pytest.fixture
def mock_client_generate():
    """Mock get_client for generate tests (also patches resolve_connection for --watch)."""
    client = _make_mock_client()
    with (
        patch("docsfy.cli.main.get_client", return_value=client),
        patch(
            "docsfy.cli.config_cmd.load_config",
            return_value={
                "default": {"server": "dev"},
                "servers": {
                    "dev": {
                        "url": "https://example.com",
                        "username": "admin",
                        "password": "test-key",  # pragma: allowlist secret
                    }
                },
            },
        ),
    ):
        yield client


class TestListProjects:
    def test_list_projects_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = _make_response(json_data={"projects": []})
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No projects found" in result.output

    def test_list_projects_table(self, mock_client: MagicMock) -> None:
        projects = [
            {
                "name": "my-repo",
                "branch": "main",
                "ai_provider": "cursor",
                "ai_model": "gpt-5",
                "status": "ready",
                "owner": "admin",
                "page_count": 5,
            },
            {
                "name": "other-repo",
                "branch": "dev",
                "ai_provider": "claude",
                "ai_model": "sonnet",
                "status": "generating",
                "owner": "user1",
                "page_count": None,
            },
        ]
        mock_client.get.return_value = _make_response(json_data={"projects": projects})
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "my-repo" in result.output
        assert "other-repo" in result.output
        assert "cursor" in result.output
        assert "claude" in result.output

    def test_list_projects_json(self, mock_client: MagicMock) -> None:
        projects = [{"name": "test", "status": "ready"}]
        mock_client.get.return_value = _make_response(json_data={"projects": projects})
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "test"

    def test_list_projects_status_filter(self, mock_client: MagicMock) -> None:
        projects = [
            {"name": "a", "status": "ready"},
            {"name": "b", "status": "error"},
        ]
        mock_client.get.return_value = _make_response(json_data={"projects": projects})
        result = runner.invoke(app, ["list", "--status", "ready"])
        assert result.exit_code == 0
        assert "a" in result.output
        assert "b" not in result.output

    def test_list_projects_provider_filter(self, mock_client: MagicMock) -> None:
        projects = [
            {"name": "a", "ai_provider": "cursor", "status": "ready"},
            {"name": "b", "ai_provider": "claude", "status": "ready"},
        ]
        mock_client.get.return_value = _make_response(json_data={"projects": projects})
        result = runner.invoke(app, ["list", "--provider", "cursor"])
        assert result.exit_code == 0
        assert "a" in result.output
        # "b" might appear in table headers; check it's not in data rows
        lines = result.output.strip().split("\n")
        data_lines = lines[2:]  # skip header and separator
        assert not any("claude" in line for line in data_lines)


class TestStatus:
    def test_status_all_variants(self, mock_client: MagicMock) -> None:
        variants = [
            {
                "name": "my-repo",
                "branch": "main",
                "ai_provider": "cursor",
                "ai_model": "gpt-5",
                "status": "ready",
                "owner": "admin",
                "page_count": 3,
                "last_generated": "2026-01-01T00:00:00",
                "last_commit_sha": "abcdef1234567890",  # pragma: allowlist secret
            }
        ]
        mock_client.get.return_value = _make_response(
            json_data={"name": "my-repo", "variants": variants}
        )
        result = runner.invoke(app, ["status", "my-repo"])
        assert result.exit_code == 0
        assert "my-repo" in result.output
        assert "ready" in result.output
        assert "abcdef12" in result.output

    def test_status_specific_variant(self, mock_client: MagicMock) -> None:
        variant = {
            "name": "my-repo",
            "branch": "main",
            "ai_provider": "cursor",
            "ai_model": "gpt-5",
            "status": "ready",
            "owner": "admin",
            "page_count": 3,
        }
        mock_client.get.return_value = _make_response(json_data=variant)
        result = runner.invoke(
            app,
            ["status", "my-repo", "-b", "main", "-p", "cursor", "-m", "gpt-5"],
        )
        assert result.exit_code == 0
        assert "ready" in result.output

    def test_status_json_output(self, mock_client: MagicMock) -> None:
        variants = [{"name": "test", "status": "ready"}]
        mock_client.get.return_value = _make_response(
            json_data={"name": "test", "variants": variants}
        )
        result = runner.invoke(app, ["status", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "variants" in data


class TestDelete:
    def test_delete_requires_args(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["delete", "my-repo"])
        assert result.exit_code == 1
        assert "Specify --branch" in result.output

    def test_delete_variant_confirmed(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = _make_response(
            json_data={"deleted": "my-repo/main/cursor/gpt-5"},
            method="DELETE",
        )
        result = runner.invoke(
            app,
            [
                "delete",
                "my-repo",
                "-b",
                "main",
                "-p",
                "cursor",
                "-m",
                "gpt-5",
                "--yes",
            ],
        )
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_delete_all_confirmed(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = _make_response(
            json_data={"deleted": "my-repo"}, method="DELETE"
        )
        result = runner.invoke(app, ["delete", "my-repo", "--all", "--yes"])
        assert result.exit_code == 0
        assert "Deleted all variants" in result.output

    def test_delete_aborted(self, mock_client: MagicMock) -> None:
        result = runner.invoke(
            app,
            [
                "delete",
                "my-repo",
                "-b",
                "main",
                "-p",
                "cursor",
                "-m",
                "gpt-5",
            ],
            input="n\n",
        )
        assert result.exit_code == 0
        assert "Aborted" in result.output


class TestAbort:
    def test_abort_by_name(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={"aborted": "my-repo"}, method="POST"
        )
        result = runner.invoke(app, ["abort", "my-repo"])
        assert result.exit_code == 0
        assert "Aborted" in result.output

    def test_abort_specific_variant(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={"aborted": "my-repo/main/cursor/gpt-5"},
            method="POST",
        )
        result = runner.invoke(
            app,
            [
                "abort",
                "my-repo",
                "-b",
                "main",
                "-p",
                "cursor",
                "-m",
                "gpt-5",
            ],
        )
        assert result.exit_code == 0
        assert "Aborted" in result.output


class TestGenerate:
    def test_generate_basic(self, mock_client_generate: MagicMock) -> None:
        mock_client_generate.post.return_value = _make_response(
            json_data={"project": "my-repo", "status": "generating", "branch": "main"},
            method="POST",
        )
        result = runner.invoke(
            app,
            ["generate", "https://github.com/org/my-repo"],
        )
        assert result.exit_code == 0
        assert "my-repo" in result.output
        assert "generating" in result.output

    def test_generate_with_options(self, mock_client_generate: MagicMock) -> None:
        mock_client_generate.post.return_value = _make_response(
            json_data={"project": "my-repo", "status": "generating", "branch": "dev"},
            method="POST",
        )
        result = runner.invoke(
            app,
            [
                "generate",
                "https://github.com/org/my-repo",
                "--branch",
                "dev",
                "--provider",
                "claude",
                "--model",
                "sonnet",
                "--force",
            ],
        )
        assert result.exit_code == 0
        assert "dev" in result.output


class TestModels:
    def test_models_lists_providers(self, mock_client: MagicMock) -> None:
        mock_client.get_models.return_value = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "cursor": [{"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"}],
                "claude": [{"id": "sonnet-4", "name": "Sonnet 4"}],
            },
        }
        result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "gemini" in result.output
        assert "cursor" in result.output

    def test_models_shows_default_markers(self, mock_client: MagicMock) -> None:
        mock_client.get_models.return_value = {
            "providers": ["claude", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "cursor": [
                    {"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"},
                    {"id": "gpt-4", "name": "GPT 4"},
                ],
            },
        }
        result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        # Provider marked as default
        assert "Provider: cursor (default)" in result.output
        # Model marked as default
        assert "gpt-5.4-xhigh-fast  (default)" in result.output
        # Non-default model has no marker
        lines = result.output.strip().split("\n")
        gpt4_lines = [line for line in lines if "gpt-4" in line]
        assert gpt4_lines
        assert "(default)" not in gpt4_lines[0]

    def test_models_filter_by_provider(self, mock_client: MagicMock) -> None:
        mock_client.get_models.return_value = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "claude": [{"id": "sonnet-4", "name": "Sonnet 4"}],
                "cursor": [{"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"}],
            },
        }
        result = runner.invoke(app, ["models", "--provider", "claude"])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "cursor" not in result.output.lower().replace("provider: cursor", "")
        # Only claude provider section should appear
        assert "Provider: claude" in result.output

    def test_models_filter_unknown_provider(self, mock_client: MagicMock) -> None:
        mock_client.get_models.return_value = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {},
        }
        result = runner.invoke(app, ["models", "--provider", "invalid"])
        assert result.exit_code == 1
        assert "Unknown provider" in result.output

    def test_models_no_models_available(self, mock_client: MagicMock) -> None:
        mock_client.get_models.return_value = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {},
        }
        result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        assert "(no models available)" in result.output

    def test_models_json_output(self, mock_client: MagicMock) -> None:
        api_data = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "cursor": [{"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"}],
                "claude": [{"id": "sonnet-4", "name": "Sonnet 4"}],
            },
        }
        mock_client.get_models.return_value = api_data
        result = runner.invoke(app, ["models", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == api_data

    def test_models_refresh_calls_refresh_method(self, mock_client: MagicMock) -> None:
        mock_client.refresh_models.return_value = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "cursor": [{"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"}],
            },
        }
        result = runner.invoke(app, ["models", "--refresh"])
        assert result.exit_code == 0
        mock_client.refresh_models.assert_called_once()
        mock_client.get_models.assert_not_called()
        assert "Models refreshed from AI providers" in result.output

    def test_models_refresh_json_no_confirmation(self, mock_client: MagicMock) -> None:
        api_data = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "cursor": [{"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"}],
            },
        }
        mock_client.refresh_models.return_value = api_data
        result = runner.invoke(app, ["models", "--refresh", "--json"])
        assert result.exit_code == 0
        mock_client.refresh_models.assert_called_once()
        assert "Models refreshed" not in result.output
        data = json.loads(result.output)
        assert data == api_data

    def test_models_json_filtered_by_provider(self, mock_client: MagicMock) -> None:
        mock_client.get_models.return_value = {
            "providers": ["claude", "gemini", "cursor"],
            "default_provider": "cursor",
            "default_model": "gpt-5.4-xhigh-fast",
            "available_models": {
                "cursor": [{"id": "gpt-5.4-xhigh-fast", "name": "GPT 5.4"}],
                "claude": [{"id": "sonnet-4", "name": "Sonnet 4"}],
            },
        }
        result = runner.invoke(app, ["models", "--json", "--provider", "claude"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["providers"] == ["claude"]
        assert data["default_provider"] == "cursor"
        assert data["default_model"] == "gpt-5.4-xhigh-fast"
        assert data["available_models"] == {
            "claude": [{"id": "sonnet-4", "name": "Sonnet 4"}]
        }
        # Must not contain other providers' models
        assert "cursor" not in data["available_models"]


def _write_nested_docs_tarball(
    output_path: Path,
    *,
    nested_name: str = "my-repo-main-cursor-gpt-5",
) -> None:
    """Write a minimal nested docs tar.gz to *output_path*."""
    import io
    import tarfile as tf

    buf = io.BytesIO()
    with tf.open(fileobj=buf, mode="w:gz") as tar:
        for filename, content in (
            ("index.html", b"<html>test</html>"),
            ("page.html", b"<html>page</html>"),
        ):
            info = tf.TarInfo(name=f"{nested_name}/{filename}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    buf.seek(0)
    output_path.write_bytes(buf.read())


_DOWNLOAD_VARIANT_ARGS = [
    "download",
    "my-repo",
    "-b",
    "main",
    "-p",
    "cursor",
    "-m",
    "gpt-5",
]


class TestDownload:
    def test_download_to_file(self, mock_client: MagicMock, tmp_path: Path) -> None:
        # Mock the download method to write fake data
        def fake_download(url_path: str, output_path: Path) -> None:
            output_path.write_bytes(b"fake-tar-data")

        mock_client.download.side_effect = fake_download

        # Patch Path.cwd to use tmp_path
        with patch("docsfy.cli.projects.Path") as mock_path_cls:
            mock_path_cls.cwd.return_value = tmp_path
            # Make Path() calls for actual paths still work
            mock_path_cls.side_effect = lambda *args, **kwargs: Path(*args, **kwargs)

            result = runner.invoke(
                app,
                [*_DOWNLOAD_VARIANT_ARGS],
            )
        assert result.exit_code == 0

    def test_download_flatten_requires_output(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--flatten without --output should fail."""
        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--flatten"],
        )
        assert result.exit_code == 1
        assert "--flatten requires --output" in result.output

    def test_download_flatten(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """--flatten should move files from nested dir to output root."""
        output_dir = tmp_path / "docs"
        mock_client.download.side_effect = lambda url_path, output_path: (
            _write_nested_docs_tarball(output_path)
        )

        result = runner.invoke(
            app,
            [
                *_DOWNLOAD_VARIANT_ARGS,
                "--output",
                str(output_dir),
                "--flatten",
            ],
        )
        assert result.exit_code == 0
        assert "flattened" in result.output.lower()
        # Files should be directly in output_dir, not in a subdirectory
        assert (output_dir / "index.html").exists()
        assert (output_dir / "page.html").exists()
        # Nested directory should be gone
        assert not (output_dir / "my-repo-main-cursor-gpt-5").exists()

    def test_download_flatten_clears_stale_files(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--output --flatten should remove orphan files left from a prior extract."""
        output_dir = tmp_path / "docs"
        output_dir.mkdir()
        orphan_md = output_dir / "old-recipe.md"
        orphan_html = output_dir / "orphan.html"
        orphan_md.write_text("stale recipe")
        orphan_html.write_text("<html>orphan</html>")

        mock_client.download.side_effect = lambda url_path, output_path: (
            _write_nested_docs_tarball(output_path)
        )

        result = runner.invoke(
            app,
            [
                *_DOWNLOAD_VARIANT_ARGS,
                "--output",
                str(output_dir),
                "--flatten",
            ],
        )
        assert result.exit_code == 0
        assert "flattened" in result.output.lower()
        assert (output_dir / "index.html").exists()
        assert (output_dir / "page.html").exists()
        assert not orphan_md.exists()
        assert not orphan_html.exists()
        assert not (output_dir / "my-repo-main-cursor-gpt-5").exists()

    def test_download_output_clears_stale_files_without_flatten(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--output without --flatten should still remove orphan files."""
        output_dir = tmp_path / "docs"
        output_dir.mkdir()
        orphan = output_dir / "orphan-stale.md"
        orphan.write_text("stale")

        mock_client.download.side_effect = lambda url_path, output_path: (
            _write_nested_docs_tarball(output_path)
        )

        result = runner.invoke(
            app,
            [
                *_DOWNLOAD_VARIANT_ARGS,
                "--output",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Extracted to" in result.output
        assert not orphan.exists()
        assert (output_dir / "my-repo-main-cursor-gpt-5" / "index.html").exists()

    def test_download_failure_leaves_orphans(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Download errors must not clear existing output contents."""
        output_dir = tmp_path / "docs"
        output_dir.mkdir()
        orphan = output_dir / "orphan-stale.md"
        orphan.write_text("keep me")

        mock_client.download.side_effect = RuntimeError("network fail")

        result = runner.invoke(
            app,
            [
                *_DOWNLOAD_VARIANT_ARGS,
                "--output",
                str(output_dir),
                "--flatten",
            ],
        )
        assert result.exit_code != 0
        assert orphan.exists()
        assert orphan.read_text() == "keep me"
        mock_client.download.assert_called_once()

    def test_download_refuses_root(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", "/"],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        mock_client.download.assert_not_called()

    def test_download_refuses_home(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", str(Path.home())],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        mock_client.download.assert_not_called()

    @pytest.mark.parametrize(
        "unsafe_path",
        ["/dev", "/proc", "/sys", "/run", "/var/tmp"],
        ids=["dev", "proc", "sys", "run", "var_tmp"],
    )
    def test_download_refuses_system_roots(
        self, mock_client: MagicMock, unsafe_path: str
    ) -> None:
        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", unsafe_path],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        mock_client.download.assert_not_called()

    def test_download_refuses_cwd_ancestor(
        self, mock_client: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = tmp_path / "workdir"
        nested.mkdir()
        monkeypatch.chdir(nested)
        keep = tmp_path / "keep.txt"
        keep.write_text("do not wipe")

        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", ".."],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        assert keep.exists()
        mock_client.download.assert_not_called()

    def test_download_refuses_cwd(
        self, mock_client: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        orphan = tmp_path / "orphan.txt"
        orphan.write_text("keep")

        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", "."],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        assert orphan.exists()
        mock_client.download.assert_not_called()

    def test_download_refuses_symlink(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        sensitive = tmp_path / "sensitive"
        sensitive.mkdir()
        keep = sensitive / "keep.txt"
        keep.write_text("do not wipe")
        link = tmp_path / "out-link"
        link.symlink_to(sensitive)

        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", str(link)],
        )
        assert result.exit_code == 1
        assert "Refusing to clear symlink path" in result.output
        assert keep.exists()
        mock_client.download.assert_not_called()

    def test_download_refuses_dangling_symlink(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        link = tmp_path / "dangling-out"
        link.symlink_to(tmp_path / "missing-target")

        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", str(link)],
        )
        assert result.exit_code == 1
        assert "Refusing to clear symlink path" in result.output
        mock_client.download.assert_not_called()

    def test_download_refuses_etc_nginx(self, mock_client: MagicMock) -> None:
        """Descendants of sensitive trees (e.g. /etc) must be refused."""
        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", "/etc/nginx"],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        mock_client.download.assert_not_called()

    def test_download_refuses_path_resolving_under_etc(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """A non-symlink path whose resolve() lands under /etc must be refused."""
        etc_link = tmp_path / "etc-link"
        etc_link.symlink_to("/etc")
        # Path itself is not a symlink; a parent symlink makes resolve() → /etc/nginx.
        target = etc_link / "nginx"

        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", str(target)],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        mock_client.download.assert_not_called()

    def test_download_refuses_var_log(self, mock_client: MagicMock) -> None:
        result = runner.invoke(
            app,
            [*_DOWNLOAD_VARIANT_ARGS, "--output", "/var/log"],
        )
        assert result.exit_code == 1
        assert "Refusing to clear dangerous path" in result.output
        mock_client.download.assert_not_called()

    def test_refuse_allows_tmp_and_var_tmp_descendants(self, tmp_path: Path) -> None:
        """/tmp/... and /var/tmp/... descendants are allowed; exact roots are not."""
        import typer

        from docsfy.cli.projects import _refuse_unsafe_clear_target

        home_sub = Path.home() / ".docsfy-test-clear-ok"
        # Exact roots still refused.
        for exact in ("/tmp", "/var/tmp"):
            with pytest.raises(typer.Exit):
                _refuse_unsafe_clear_target(Path(exact))

        # Descendants / home subdir are allowed (no Exit).
        _refuse_unsafe_clear_target(tmp_path / "out")
        # Only assert allow for paths we can create under the sandbox when
        # /tmp or /var/tmp may be unusable; exercise the allow branch via
        # resolved paths that are under those trees when they exist.
        for allowed in (
            Path("/tmp") / "docsfy-clear-ok",
            Path("/var/tmp") / "docsfy-clear-ok",
        ):
            if allowed.parent.is_dir():
                _refuse_unsafe_clear_target(allowed)
        _refuse_unsafe_clear_target(home_sub)

    def test_move_directory_entries_replaces_same_named(self, tmp_path: Path) -> None:
        """Restore/install must replace same-named dirs, not nest into them."""
        from docsfy.cli.projects import _move_directory_entries

        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "docs").mkdir()
        (src / "docs" / "new.html").write_text("new")
        (dest / "docs").mkdir()
        (dest / "docs" / "old.html").write_text("old")

        _move_directory_entries(src, dest)

        assert (dest / "docs" / "new.html").read_text() == "new"
        assert not (dest / "docs" / "old.html").exists()
        assert not (dest / "docs" / "docs").exists()
        assert list(src.iterdir()) == []

    def test_replace_restores_on_install_failure(self, tmp_path: Path) -> None:
        """Install failure after aside move must restore originals and re-raise."""
        from docsfy.cli.projects import (
            _move_directory_entries,
            _replace_directory_contents,
        )

        output_dir = tmp_path / "out"
        source_dir = tmp_path / "src"
        output_dir.mkdir()
        source_dir.mkdir()
        (output_dir / "old.txt").write_text("keep-me")
        (source_dir / "new.txt").write_text("new")

        calls = {"n": 0}
        real_move = _move_directory_entries

        def flaky_move(src: Path, dest: Path) -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("install boom")
            real_move(src, dest)

        with patch(
            "docsfy.cli.projects._move_directory_entries", side_effect=flaky_move
        ):
            with pytest.raises(RuntimeError, match="install boom"):
                _replace_directory_contents(output_dir, source_dir)

        assert (output_dir / "old.txt").read_text() == "keep-me"
        assert not (output_dir / "new.txt").exists()
        assert list(tmp_path.glob(".docsfy-aside-*")) == []

    def test_replace_restores_on_keyboard_interrupt(self, tmp_path: Path) -> None:
        """KeyboardInterrupt during install must still restore aside contents."""
        from docsfy.cli.projects import (
            _move_directory_entries,
            _replace_directory_contents,
        )

        output_dir = tmp_path / "out"
        source_dir = tmp_path / "src"
        output_dir.mkdir()
        source_dir.mkdir()
        (output_dir / "old.txt").write_text("keep-me")
        (source_dir / "new.txt").write_text("new")

        calls = {"n": 0}
        real_move = _move_directory_entries

        def interrupt_on_install(src: Path, dest: Path) -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                raise KeyboardInterrupt
            real_move(src, dest)

        with patch(
            "docsfy.cli.projects._move_directory_entries",
            side_effect=interrupt_on_install,
        ):
            with pytest.raises(KeyboardInterrupt):
                _replace_directory_contents(output_dir, source_dir)

        assert (output_dir / "old.txt").read_text() == "keep-me"
        assert not (output_dir / "new.txt").exists()
        assert list(tmp_path.glob(".docsfy-aside-*")) == []

    def test_replace_warns_unrecovered_aside(self, tmp_path: Path) -> None:
        """When aside cannot be emptied after failure, warn instead of deleting."""
        from docsfy.cli.projects import (
            _move_directory_entries,
            _replace_directory_contents,
        )

        output_dir = tmp_path / "out"
        source_dir = tmp_path / "src"
        output_dir.mkdir()
        source_dir.mkdir()
        (output_dir / "old.txt").write_text("keep-me")
        (source_dir / "new.txt").write_text("new")

        calls = {"n": 0}
        real_move = _move_directory_entries
        real_rmdir = Path.rmdir

        def flaky_move(src: Path, dest: Path) -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("install boom")
            real_move(src, dest)

        def rmdir_fail(self: Path) -> None:
            if self.name.startswith(".docsfy-aside-"):
                # Leave a marker so rmdir would fail even if empty check passes.
                (self / ".stuck").write_text("x")
            real_rmdir(self)

        with (
            patch(
                "docsfy.cli.projects._move_directory_entries", side_effect=flaky_move
            ),
            patch.object(Path, "rmdir", rmdir_fail),
            patch("docsfy.cli.projects.typer.echo") as echo,
        ):
            with pytest.raises(RuntimeError, match="install boom"):
                _replace_directory_contents(output_dir, source_dir)

        assert (output_dir / "old.txt").read_text() == "keep-me"
        warning_calls = [
            c
            for c in echo.call_args_list
            if c.args and "unrecovered aside" in str(c.args[0])
        ]
        assert warning_calls
        asides = list(tmp_path.glob(".docsfy-aside-*"))
        assert len(asides) == 1
        assert (asides[0] / ".stuck").exists()
