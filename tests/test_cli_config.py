from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from typer.testing import CliRunner

from docsfy.cli.config_cmd import resolve_connection
from docsfy.cli.main import app

runner = CliRunner()


@pytest.fixture
def config_dir(tmp_path: Path):
    """Patch CONFIG_DIR and CONFIG_FILE to use a temp directory."""
    cfg_dir = tmp_path / ".config" / "docsfy"
    cfg_file = cfg_dir / "config.toml"
    with (
        patch("docsfy.cli.config_cmd.CONFIG_DIR", cfg_dir),
        patch("docsfy.cli.config_cmd.CONFIG_FILE", cfg_file),
    ):
        yield cfg_dir, cfg_file


class TestConfigInit:
    def test_config_init_creates_file(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        result = runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\nsecret-password\n",
        )
        assert result.exit_code == 0
        assert "Profile 'dev' saved" in result.output
        assert cfg_file.exists()

        # Verify permissions (owner-only)
        file_mode = cfg_file.stat().st_mode
        assert file_mode & stat.S_IRUSR  # owner read
        assert file_mode & stat.S_IWUSR  # owner write
        assert not file_mode & stat.S_IRGRP  # no group read
        assert not file_mode & stat.S_IROTH  # no other read

    def test_config_init_content(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="myprofile\nhttps://my-server.com\nmyuser\nmy-api-key-12345\n",
        )

        import tomllib

        with open(cfg_file, "rb") as f:
            config = tomllib.load(f)

        assert config["servers"]["myprofile"]["url"] == "https://my-server.com"
        assert config["servers"]["myprofile"]["username"] == "myuser"
        pw = config["servers"]["myprofile"]["password"]
        assert pw == "my-api-key-12345"  # pragma: allowlist secret
        assert config["default"]["server"] == "myprofile"

    def test_config_init_default_profile_name(
        self, config_dir: tuple[Path, Path]
    ) -> None:
        cfg_dir, cfg_file = config_dir
        result = runner.invoke(
            app,
            ["config", "init"],
            input="\nhttps://example.com\nadmin\npassword\n",
        )
        assert result.exit_code == 0

        import tomllib

        with open(cfg_file, "rb") as f:
            config = tomllib.load(f)

        assert "dev" in config["servers"]
        assert config["default"]["server"] == "dev"

    def test_config_init_adds_second_profile(
        self, config_dir: tuple[Path, Path]
    ) -> None:
        cfg_dir, cfg_file = config_dir
        # Create first profile
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttp://localhost:8000\nadmin\ndev-key\n",
        )
        # Create second profile
        runner.invoke(
            app,
            ["config", "init"],
            input="prod\nhttps://prod.example.com\nadmin\nprod-key\n",
        )

        import tomllib

        with open(cfg_file, "rb") as f:
            config = tomllib.load(f)

        assert "dev" in config["servers"]
        assert "prod" in config["servers"]
        # Default should still be the first one
        assert config["default"]["server"] == "dev"


class TestConfigShow:
    def test_config_show_missing(self, config_dir: tuple[Path, Path]) -> None:
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 1
        assert "Config not found" in result.output

    def test_config_show_displays_profiles(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        # Create a config with a profile
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\nsuper-secret-long-password\n",
        )
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "https://example.com" in result.output
        assert "admin" in result.output
        assert "[dev]" in result.output
        assert "(default)" in result.output
        # Password should be masked
        assert "super-secret-long-password" not in result.output
        assert "***" in result.output

    def test_config_show_short_password_masked(
        self, config_dir: tuple[Path, Path]
    ) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\nmypw\n",
        )
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "***" in result.output


class TestConfigSet:
    def test_config_set_missing_config(self, config_dir: tuple[Path, Path]) -> None:
        result = runner.invoke(app, ["config", "set", "default.server", "prod"])
        assert result.exit_code == 1

    def test_config_set_default_server(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\npassword\n",
        )
        result = runner.invoke(app, ["config", "set", "default.server", "prod"])
        assert result.exit_code == 0
        assert "Updated default.server" in result.output

        import tomllib

        with open(cfg_file, "rb") as f:
            config = tomllib.load(f)
        assert config["default"]["server"] == "prod"

    def test_config_set_server_url(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\npassword\n",
        )
        result = runner.invoke(
            app, ["config", "set", "servers.dev.url", "https://new-server.com"]
        )
        assert result.exit_code == 0
        assert "Updated servers.dev.url" in result.output

        import tomllib

        with open(cfg_file, "rb") as f:
            config = tomllib.load(f)
        assert config["servers"]["dev"]["url"] == "https://new-server.com"

    def test_config_set_invalid_key(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\npassword\n",
        )
        result = runner.invoke(app, ["config", "set", "invalid.key", "value"])
        assert result.exit_code == 1
        assert "Invalid key" in result.output

    def test_config_set_server_password(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\nold-password\n",
        )
        result = runner.invoke(
            app, ["config", "set", "servers.dev.password", "new-password"]
        )
        assert result.exit_code == 0

        import tomllib

        with open(cfg_file, "rb") as f:
            config = tomllib.load(f)
        pw = config["servers"]["dev"]["password"]
        assert pw == "new-password"  # pragma: allowlist secret


class TestResolveConnection:
    def test_explicit_host_port(self, config_dir: tuple[Path, Path]) -> None:
        url, user, pw = resolve_connection(
            server=None,
            host="myhost",
            port=9000,
            username="user1",
            password="pass1",  # pragma: allowlist secret
        )
        assert url == "https://myhost:9000"
        assert user == "user1"
        assert pw == "pass1"

    def test_explicit_host_default_port(self, config_dir: tuple[Path, Path]) -> None:
        url, user, pw = resolve_connection(
            server=None,
            host="myhost",
            port=None,
            username="user1",
            password="pass1",  # pragma: allowlist secret
        )
        assert url == "https://myhost:8000"

    def test_server_profile(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="prod\nhttps://prod.example.com\nproduser\nprod-key\n",
        )
        url, user, pw = resolve_connection(
            server="prod",
            host=None,
            port=None,
            username=None,
            password=None,
        )
        assert url == "https://prod.example.com"
        assert user == "produser"
        assert pw == "prod-key"

    def test_default_profile(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttp://localhost:8000\nadmin\ndev-key\n",
        )
        url, user, pw = resolve_connection(
            server=None,
            host=None,
            port=None,
            username=None,
            password=None,
        )
        assert url == "http://localhost:8000"
        assert user == "admin"
        assert pw == "dev-key"

    def test_partial_override(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="prod\nhttps://prod.example.com\nproduser\nprod-key\n",
        )
        url, user, pw = resolve_connection(
            server="prod",
            host=None,
            port=None,
            username="other-user",
            password=None,
        )
        assert url == "https://prod.example.com"
        assert user == "other-user"
        assert pw == "prod-key"

    def test_nonexistent_profile_error(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttp://localhost:8000\nadmin\ndev-key\n",
        )
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            resolve_connection(
                server="nonexistent",
                host=None,
                port=None,
                username=None,
                password=None,
            )

    def test_no_config_no_flags_error(self, config_dir: tuple[Path, Path]) -> None:
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            resolve_connection(
                server=None,
                host=None,
                port=None,
                username=None,
                password=None,
            )

    def test_host_overrides_profile_url(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\nmy-key\n",
        )
        url, user, pw = resolve_connection(
            server="dev",
            host="override-host",
            port=3000,
            username=None,
            password=None,
        )
        # --host overrides the profile URL but preserves the profile's scheme
        assert url == "https://override-host:3000"
        # Credentials still come from the profile
        assert user == "admin"
        assert pw == "my-key"


class TestHealth:
    def test_health_no_config(self, config_dir: tuple[Path, Path]) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 1

    def test_health_success(self, config_dir: tuple[Path, Path]) -> None:
        cfg_dir, cfg_file = config_dir
        runner.invoke(
            app,
            ["config", "init"],
            input="dev\nhttps://example.com\nadmin\npassword\n",
        )

        import httpx

        mock_response = httpx.Response(
            200,
            json={"status": "ok"},
            request=httpx.Request("GET", "https://example.com/health"),
        )

        with patch("docsfy.cli.client.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.get.return_value = mock_response
            result = runner.invoke(app, ["health"])

        assert result.exit_code == 0
        assert "ok" in result.output

    def test_health_with_host_flag(self, config_dir: tuple[Path, Path]) -> None:
        import httpx

        mock_response = httpx.Response(
            200,
            json={"status": "ok"},
            request=httpx.Request("GET", "http://myhost:9000/health"),
        )

        with patch("docsfy.cli.client.httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.get.return_value = mock_response
            result = runner.invoke(
                app,
                [
                    "--host",
                    "myhost",
                    "--port",
                    "9000",
                    "-u",
                    "admin",
                    "-p",
                    "key",
                    "health",
                ],
            )

        assert result.exit_code == 0
        assert "ok" in result.output
