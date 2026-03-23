from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

import typer

from docsfy.cli.admin import admin_app
from docsfy.cli.config_cmd import config_app, resolve_connection

if TYPE_CHECKING:
    from docsfy.cli.client import DocsfyClient

app = typer.Typer(
    name="docsfy",
    help="docsfy CLI -- AI-powered documentation generator",
    no_args_is_help=True,
)
app.add_typer(config_app)
app.add_typer(admin_app)

# Module-level state populated by the app callback with global CLI options.
_state: dict[str, Any] = {}


def get_client() -> DocsfyClient:
    """Build a DocsfyClient from the resolved global connection options."""
    from docsfy.cli.client import DocsfyClient as _DocsfyClient

    url, username, password = resolve_connection(
        server=_state.get("server"),
        host=_state.get("host"),
        port=_state.get("port"),
        username=_state.get("username"),
        password=_state.get("password"),
    )
    return _DocsfyClient(server_url=url, username=username, password=password)


@app.callback()
def main_callback(
    server: Optional[str] = typer.Option(  # noqa: M511
        None, "--server", "-s", help="Server profile name from config"
    ),
    host: Optional[str] = typer.Option(  # noqa: M511
        None, "--host", help="Server host (overrides config)"
    ),
    port: Optional[int] = typer.Option(  # noqa: M511
        None, "--port", help="Server port (default 8000)"
    ),
    username: Optional[str] = typer.Option(  # noqa: M511
        None, "--username", "-u", help="Username"
    ),
    password: Optional[str] = typer.Option(  # noqa: M511
        None, "--password", "-p", help="Password/API key"
    ),
) -> None:
    """docsfy CLI -- AI-powered documentation generator"""
    _state["server"] = server
    _state["host"] = host
    _state["port"] = port
    _state["username"] = username
    _state["password"] = password


# Import standalone commands after app is defined to avoid circular imports
from docsfy.cli.generate import generate  # noqa: E402
from docsfy.cli.projects import abort, delete, download, list_projects, status  # noqa: E402

app.command("generate")(generate)
app.command("list")(list_projects)
app.command("status")(status)
app.command("delete")(delete)
app.command("abort")(abort)
app.command("download")(download)


@app.command("health")
def health() -> None:
    """Check server health."""
    client = get_client()
    try:
        response = client.get("/health")
        data = response.json()
        typer.echo(f"Server: {client.server_url}")
        typer.echo(f"Status: {data.get('status', 'unknown')}")
    finally:
        client.close()


def main() -> None:
    """Entry point for console_scripts."""
    app()
