from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path
from typing import Any

import tomli_w
import typer

config_app = typer.Typer(name="config", help="Manage docsfy CLI configuration")

CONFIG_DIR = Path.home() / ".config" / "docsfy"
CONFIG_FILE = CONFIG_DIR / "config.toml"

_DEFAULT_PORT = 8000

_VALID_KEY_PREFIXES = frozenset({"default.", "servers."})


def load_config() -> dict[str, Any]:
    """Load and return the CLI configuration from disk."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        typer.echo(
            f"Error: Failed to parse config file {CONFIG_FILE}: {exc}",
            err=True,
        )
        raise typer.Exit(code=1) from exc


def _save_config(config: dict[str, Any]) -> None:
    """Write config to disk with secure permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, stat.S_IRWXU)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)
    os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)


def resolve_connection(
    server: str | None,
    host: str | None,
    port: int | None,
    username: str | None,
    password: str | None,
) -> tuple[str, str, str]:
    """Resolve connection parameters from CLI flags, config profiles, or defaults.

    Priority (highest to lowest):
    1. Explicit CLI flags (host, port, username, password)
    2. Server profile from --server flag
    3. Default server profile from config [default].server
    4. Error if nothing is configured

    Returns:
        Tuple of (url, username, password).

    Raises:
        typer.Exit: If no server can be resolved.
    """
    config = load_config()

    # Determine which profile to load (--server flag or default)
    profile: dict[str, Any] = {}
    profile_name = server or config.get("default", {}).get("server")

    if profile_name:
        profile = config.get("servers", {}).get(profile_name, {})
        if not profile and server:
            # Explicit --server flag pointed to a non-existent profile
            typer.echo(
                f"Server profile '{server}' not found in config. "
                f"Available: {', '.join(config.get('servers', {}).keys()) or 'none'}",
                err=True,
            )
            raise typer.Exit(code=1)

    # Resolve URL: explicit --host/--port wins over profile
    if host:
        resolved_port = port or _DEFAULT_PORT
        # Preserve scheme from profile if available, otherwise default to https
        profile_url = profile.get("url", "")
        if profile_url.startswith("http://"):
            scheme = "http"
        else:
            scheme = "https"
        url = f"{scheme}://{host}:{resolved_port}"
    else:
        url = profile.get("url", "")
        if not url:
            # No URL from profile and no --host flag
            if not profile_name:
                typer.echo(
                    "No server configured. Use --server, --host, or run "
                    "'docsfy config init'.",
                    err=True,
                )
                raise typer.Exit(code=1)

    # Resolve credentials: explicit flags win over profile
    resolved_username = username or profile.get("username", "")
    resolved_password = password or profile.get("password", "")

    return url, resolved_username, resolved_password


@config_app.command("init")
def config_init() -> None:
    """Interactive config setup -- creates a server profile."""
    profile_name = typer.prompt("Profile name", default="dev")
    server_url = typer.prompt("Server URL")
    username_val = typer.prompt("Username")
    password_val = typer.prompt("Password", hide_input=True)

    config = load_config()

    # Set up the profile
    if "servers" not in config:
        config["servers"] = {}
    config["servers"][profile_name] = {
        "url": server_url,
        "username": username_val,
        "password": password_val,
    }

    # Set as default if no default exists yet
    if "default" not in config:
        config["default"] = {"server": profile_name}

    _save_config(config)
    typer.echo(f"Profile '{profile_name}' saved to {CONFIG_FILE}")


@config_app.command("show")
def config_show() -> None:
    """Display all server profiles with masked passwords."""
    config = load_config()
    if not config:
        typer.echo("Config not found. Run 'docsfy config init' to set up.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Config file: {CONFIG_FILE}")

    default_server = config.get("default", {}).get("server", "not set")
    typer.echo(f"Default server: {default_server}")
    typer.echo("")

    servers = config.get("servers", {})
    if not servers:
        typer.echo("No server profiles configured.")
        return

    for name, profile in servers.items():
        marker = " (default)" if name == default_server else ""
        typer.echo(f"[{name}]{marker}")
        typer.echo(f"  URL:      {profile.get('url', 'not set')}")
        typer.echo(f"  Username: {profile.get('username', 'not set')}")
        pw = profile.get("password", "")
        masked = pw[:2] + "***" if len(pw) > 2 else "***"
        typer.echo(f"  Password: {masked}")
        typer.echo("")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a config value. Examples: default.server, servers.dev.url, servers.dev.username"""
    config = load_config()
    if not config:
        typer.echo("Config not found. Run 'docsfy config init' first.", err=True)
        raise typer.Exit(code=1)

    parts = key.split(".")
    if not any(key.startswith(prefix) for prefix in _VALID_KEY_PREFIXES):
        typer.echo(
            f"Invalid key: {key}. Keys must start with 'default.' or 'servers.'",
            err=True,
        )
        raise typer.Exit(code=1)

    # Navigate to the correct nested dict and set the value
    current = config
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value

    _save_config(config)
    typer.echo(f"Updated {key}")
