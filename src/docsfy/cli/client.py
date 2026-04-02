from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import typer


class DocsfyClient:
    """HTTP client wrapper for the docsfy server API."""

    def __init__(self, server_url: str, username: str, password: str) -> None:
        self.server_url = server_url.rstrip("/")
        # username is stored for display/debugging; auth uses password as Bearer token
        self.username = username
        self.password = password
        self._client = httpx.Client(
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {self.password}"},
            timeout=30.0,
            follow_redirects=False,
        )

    def get(self, path: str, **params: str) -> httpx.Response:
        """Perform a GET request."""
        response = self._client.get(path, params=params)
        self._check_error(response)
        return response

    def post(self, path: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Perform a POST request."""
        response = self._client.post(path, json=json)
        self._check_error(response)
        return response

    def delete(self, path: str, **params: str) -> httpx.Response:
        """Perform a DELETE request."""
        response = self._client.delete(path, params=params)
        self._check_error(response)
        return response

    def get_models(self) -> dict[str, Any]:
        """Fetch available AI providers and known models."""
        response = self.get("/api/models")
        return response.json()

    def download(self, path: str, output_path: Path) -> None:
        """Stream-download a file to the given path using atomic write."""
        import tempfile

        # Write to a temp file in the same directory, then atomically rename.
        # This avoids leaving a partial file at the target path on failure.
        tmp_fd = None
        tmp_path = None
        try:
            tmp_fd, tmp_name = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
            tmp_path = Path(tmp_name)
            with self._client.stream("GET", path) as response:
                self._check_error(response)
                for chunk in response.iter_bytes(8192):
                    os.write(tmp_fd, chunk)
            os.close(tmp_fd)
            tmp_fd = None
            tmp_path.replace(output_path)
        except Exception:
            if tmp_fd is not None:
                os.close(tmp_fd)
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def _check_error(self, response: httpx.Response) -> None:
        """Print error details and exit on HTTP errors."""
        if response.is_redirect:
            location = response.headers.get("location", "?")
            typer.echo(
                f"Error: Server redirected to {location}. Check the server URL.",
                err=True,
            )
            raise typer.Exit(code=1)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.reason_phrase)
            except (json.JSONDecodeError, ValueError):
                detail = response.reason_phrase
            typer.echo(f"Error ({response.status_code}): {detail}", err=True)
            raise typer.Exit(code=1)
