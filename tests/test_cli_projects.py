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
                [
                    "download",
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

    def test_download_flatten_requires_output(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--flatten without --output should fail."""
        result = runner.invoke(
            app,
            [
                "download",
                "my-repo",
                "-b",
                "main",
                "-p",
                "cursor",
                "-m",
                "gpt-5",
                "--flatten",
            ],
        )
        assert result.exit_code == 1
        assert "--flatten requires --output" in result.output

    def test_download_flatten(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """--flatten should move files from nested dir to output root."""
        output_dir = tmp_path / "docs"

        def fake_download(url_path: str, output_path: Path) -> None:
            # Create a real tar.gz with a nested directory
            import io
            import tarfile as tf

            buf = io.BytesIO()
            with tf.open(fileobj=buf, mode="w:gz") as tar:
                # Add a nested directory with files
                info = tf.TarInfo(name="my-repo-main-cursor-gpt-5/index.html")
                content = b"<html>test</html>"
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))

                info2 = tf.TarInfo(name="my-repo-main-cursor-gpt-5/page.html")
                content2 = b"<html>page</html>"
                info2.size = len(content2)
                tar.addfile(info2, io.BytesIO(content2))

            buf.seek(0)
            output_path.write_bytes(buf.read())

        mock_client.download.side_effect = fake_download

        result = runner.invoke(
            app,
            [
                "download",
                "my-repo",
                "-b",
                "main",
                "-p",
                "cursor",
                "-m",
                "gpt-5",
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
