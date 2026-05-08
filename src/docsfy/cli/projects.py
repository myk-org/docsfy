from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Annotated, Any, Optional

import httpx
import typer

from docsfy.cli.formatting import print_table
from docsfy.models import is_uuid


def _resolve_generation_id(
    client: httpx.Client,
    name: str,
    branch: str | None,
    provider: str | None,
    model: str | None,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    """If name is a UUID, resolve it to (name, branch, provider, model, owner) via API. Otherwise return as-is."""
    if not is_uuid(name):
        return name, branch, provider, model, None
    response = client.get(f"/api/projects/by-id/{name}")
    if response.status_code == 404:
        typer.echo(f"Generation ID not found: {name}", err=True)
        raise typer.Exit(1)
    if not response.is_success:
        typer.echo(
            f"Failed to resolve generation ID: HTTP {response.status_code}",
            err=True,
        )
        raise typer.Exit(1)
    data = response.json()
    return (
        data["name"],
        branch or data["branch"],
        provider or data["ai_provider"],
        model or data["ai_model"],
        data.get("owner"),
    )


def list_projects(
    status_filter: Optional[str] = typer.Option(  # noqa: M511
        None, "--status", help="Filter by status (ready, generating, error)"
    ),
    provider_filter: Optional[str] = typer.Option(  # noqa: M511
        None, "--provider", help="Filter by AI provider"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: M511
) -> None:
    """List all projects."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        response = client.get("/api/status")
        data = response.json()
        projects = data.get("projects", [])

        if status_filter:
            projects = [p for p in projects if p.get("status") == status_filter]
        if provider_filter:
            projects = [p for p in projects if p.get("ai_provider") == provider_filter]

        if output_json:
            typer.echo(json.dumps(projects, indent=2))
            return

        if not projects:
            typer.echo("No projects found.")
            return

        rows = []
        for p in projects:
            rows.append(
                [
                    str(p.get("name", "")),
                    str(p.get("branch", "main")),
                    str(p.get("ai_provider", "")),
                    str(p.get("ai_model", "")),
                    str(p.get("status", "")),
                    str(p.get("owner", "")),
                    str(p.get("page_count", "") or ""),
                    str(p.get("generation_id", "") or ""),
                ]
            )

        print_table(
            [
                "NAME",
                "BRANCH",
                "PROVIDER",
                "MODEL",
                "STATUS",
                "OWNER",
                "PAGES",
                "GEN ID",
            ],
            rows,
        )
    finally:
        client.close()


def status(
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),  # noqa: M511
    branch: Optional[str] = typer.Option(  # noqa: M511
        None, "--branch", "-b", help="Filter by branch"
    ),
    provider: Optional[str] = typer.Option(  # noqa: M511
        None, "--provider", "-p", help="Filter by provider"
    ),
    model: Optional[str] = typer.Option(  # noqa: M511
        None, "--model", "-m", help="Filter by model"
    ),
    owner: Optional[str] = typer.Option(  # noqa: M511
        None, "--owner", help="Project owner (for admin disambiguation)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: M511
) -> None:
    """Show status of a project and its variants."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        # Resolve UUID if name looks like one
        name, branch, provider, model, resolved_owner = _resolve_generation_id(
            client, name, branch, provider, model
        )
        if resolved_owner and not owner:
            owner = resolved_owner

        owner_qs = f"?owner={owner}" if owner else ""

        # If all three are specified, get the specific variant
        if branch and provider and model:
            response = client.get(
                f"/api/projects/{name}/{branch}/{provider}/{model}{owner_qs}"
            )
            variant = response.json()
            if output_json:
                typer.echo(json.dumps(variant, indent=2))
            else:
                _print_variant_detail(variant)
            return

        # Otherwise get all variants
        response = client.get(f"/api/projects/{name}")
        data = response.json()
        variants = data.get("variants", [])

        # Apply filters
        if branch:
            variants = [v for v in variants if v.get("branch") == branch]
        if provider:
            variants = [v for v in variants if v.get("ai_provider") == provider]
        if model:
            variants = [v for v in variants if v.get("ai_model") == model]

        if output_json:
            typer.echo(json.dumps({"name": name, "variants": variants}, indent=2))
            return

        if not variants:
            typer.echo(f"No variants found for '{name}'.")
            return

        typer.echo(f"Project: {name}")
        typer.echo(f"Variants: {len(variants)}")
        typer.echo("")

        for v in variants:
            _print_variant_detail(v)
            typer.echo("")
    finally:
        client.close()


def _print_variant_detail(v: dict[str, Any]) -> None:
    """Print a single variant's details."""
    typer.echo(
        f"  {v.get('branch', 'main')}/{v.get('ai_provider', '')}/{v.get('ai_model', '')}"
    )
    if v.get("generation_id"):
        typer.echo(f"    ID:      {v['generation_id']}")
    typer.echo(f"    Status:  {v.get('status', '')}")
    typer.echo(f"    Owner:   {v.get('owner', '')}")
    if v.get("page_count"):
        typer.echo(f"    Pages:   {v['page_count']}")
    if v.get("last_generated"):
        typer.echo(f"    Updated: {v['last_generated']}")
    if v.get("last_commit_sha"):
        sha = str(v["last_commit_sha"])[:8]
        typer.echo(f"    Commit:  {sha}")
    if v.get("current_stage"):
        typer.echo(f"    Stage:   {v['current_stage']}")
    if v.get("error_message"):
        typer.echo(f"    Error:   {v['error_message']}")


def delete(
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),  # noqa: M511
    branch: Optional[str] = typer.Option(  # noqa: M511
        None, "--branch", "-b", help="Branch of variant to delete"
    ),
    provider: Optional[str] = typer.Option(  # noqa: M511
        None, "--provider", "-p", help="Provider of variant to delete"
    ),
    model: Optional[str] = typer.Option(  # noqa: M511
        None, "--model", "-m", help="Model of variant to delete"
    ),
    owner: Optional[str] = typer.Option(  # noqa: M511
        None, "--owner", help="Project owner (required for admin)"
    ),
    all_variants: bool = typer.Option(  # noqa: M511
        False, "--all", help="Delete all variants of the project"
    ),
    yes: bool = typer.Option(  # noqa: M511
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Delete a project or a specific variant."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        # Resolve UUID if name looks like one
        original_name = name
        if all_variants:
            name, _, _, _, resolved_owner = _resolve_generation_id(
                client, name, None, None, None
            )
            if is_uuid(original_name):
                typer.echo(
                    f"Warning: UUID resolved to project '{name}'. "
                    "--all will delete all variants of this project.",
                    err=True,
                )
        else:
            name, branch, provider, model, resolved_owner = _resolve_generation_id(
                client, name, branch, provider, model
            )
        if resolved_owner and not owner:
            owner = resolved_owner

        if all_variants and any([branch, provider, model]):
            typer.echo(
                "Use either --all or --branch/--provider/--model, not both.",
                err=True,
            )
            raise typer.Exit(code=1)

        owner_qs = f"?owner={owner}" if owner else ""

        if all_variants:
            if not yes:
                confirmed = typer.confirm(f"Delete ALL variants of '{name}'?")
                if not confirmed:
                    typer.echo("Aborted.")
                    raise typer.Exit()
            client.delete(f"/api/projects/{name}{owner_qs}")
            typer.echo(f"Deleted all variants of '{name}'.")

        elif branch and provider and model:
            target = f"{name}/{branch}/{provider}/{model}"
            if not yes:
                confirmed = typer.confirm(f"Delete variant '{target}'?")
                if not confirmed:
                    typer.echo("Aborted.")
                    raise typer.Exit()
            client.delete(f"/api/projects/{name}/{branch}/{provider}/{model}{owner_qs}")
            typer.echo(f"Deleted variant '{target}'.")

        else:
            typer.echo(
                "Specify --branch, --provider, and --model to delete a specific variant, "
                "or use --all to delete all variants.",
                err=True,
            )
            raise typer.Exit(code=1)
    finally:
        client.close()


def abort(
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),  # noqa: M511
    branch: Optional[str] = typer.Option(  # noqa: M511
        None, "--branch", "-b", help="Branch of variant to abort"
    ),
    provider: Optional[str] = typer.Option(  # noqa: M511
        None, "--provider", "-p", help="Provider of variant to abort"
    ),
    model: Optional[str] = typer.Option(  # noqa: M511
        None, "--model", "-m", help="Model of variant to abort"
    ),
    owner: Optional[str] = typer.Option(  # noqa: M511
        None, "--owner", help="Project owner (required for admin)"
    ),
) -> None:
    """Abort an active documentation generation."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        # Resolve UUID if name looks like one
        name, branch, provider, model, resolved_owner = _resolve_generation_id(
            client, name, branch, provider, model
        )
        if resolved_owner and not owner:
            owner = resolved_owner

        # Require all variant selectors together, or none
        variant_opts = [branch, provider, model]
        if any(variant_opts) and not all(variant_opts):
            typer.echo(
                "Specify --branch, --provider, and --model together to abort a specific variant, "
                "or omit all three to abort by project name.",
                err=True,
            )
            raise typer.Exit(code=1)

        owner_qs = f"?owner={owner}" if owner else ""

        if branch and provider and model:
            client.post(
                f"/api/projects/{name}/{branch}/{provider}/{model}/abort{owner_qs}"
            )
            typer.echo(f"Aborted generation for '{name}/{branch}/{provider}/{model}'.")
        else:
            client.post(f"/api/projects/{name}/abort{owner_qs}")
            typer.echo(f"Aborted generation for '{name}'.")
    finally:
        client.close()


def download(
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),  # noqa: M511
    branch: Optional[str] = typer.Option(  # noqa: M511
        None, "--branch", "-b", help="Branch of variant to download"
    ),
    provider: Optional[str] = typer.Option(  # noqa: M511
        None, "--provider", "-p", help="Provider of variant to download"
    ),
    model: Optional[str] = typer.Option(  # noqa: M511
        None, "--model", "-m", help="Model of variant to download"
    ),
    owner: Optional[str] = typer.Option(  # noqa: M511
        None, "--owner", help="Project owner (for admin disambiguation)"
    ),
    output: Optional[str] = typer.Option(  # noqa: M511
        None,
        "--output",
        "-o",
        help="Output directory to extract to (default: save tar.gz to current dir)",
    ),
    flatten: bool = typer.Option(  # noqa: M511
        False, "--flatten", help="Flatten extracted directory structure into output dir"
    ),
) -> None:
    """Download generated documentation as tar.gz or extract to a directory."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        # Resolve UUID if name looks like one
        name, branch, provider, model, resolved_owner = _resolve_generation_id(
            client, name, branch, provider, model
        )
        if resolved_owner and not owner:
            owner = resolved_owner

        # Require all variant selectors together, or none
        variant_opts = [branch, provider, model]
        if any(variant_opts) and not all(variant_opts):
            typer.echo(
                "Specify --branch, --provider, and --model together to download a specific variant, "
                "or omit all three to download the default variant.",
                err=True,
            )
            raise typer.Exit(code=1)

        if flatten and not output:
            typer.echo("--flatten requires --output", err=True)
            raise typer.Exit(code=1)

        owner_qs = f"?owner={owner}" if owner else ""

        if branch and provider and model:
            url_path = (
                f"/api/projects/{name}/{branch}/{provider}/{model}/download{owner_qs}"
            )
            archive_name = f"{name}-{branch}-{provider}-{model}-docs.tar.gz"
        else:
            url_path = f"/api/projects/{name}/download{owner_qs}"
            archive_name = f"{name}-docs.tar.gz"

        if output:
            # Download to a temp file and extract
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            try:
                client.download(url_path, tmp_path)
                output_dir = Path(output)
                output_dir.mkdir(parents=True, exist_ok=True)
                with tarfile.open(tmp_path, "r:gz") as tar:
                    tar.extractall(path=output_dir, filter="data")
                if flatten:
                    # Look for the expected nested directory from the archive
                    expected_name = (
                        f"{name}-{branch}-{provider}-{model}"
                        if branch and provider and model
                        else name
                    )
                    expected_dir = output_dir / expected_name
                    nested_dir: Path | None = None
                    if expected_dir.is_dir():
                        nested_dir = expected_dir
                    else:
                        # Fall back to single top-level directory
                        subdirs = [
                            d
                            for d in output_dir.iterdir()
                            if d.is_dir() and not d.name.startswith(".")
                        ]
                        if len(subdirs) == 1:
                            nested_dir = subdirs[0]
                    if nested_dir is not None:
                        # Move all contents up to the output directory
                        for item in list(nested_dir.iterdir()):
                            dest_path = output_dir / item.name
                            if dest_path.exists():
                                if dest_path.is_dir():
                                    shutil.rmtree(dest_path)
                                else:
                                    dest_path.unlink()
                            item.rename(dest_path)
                        nested_dir.rmdir()
                        typer.echo(f"Extracted and flattened to {output_dir}")
                    else:
                        typer.echo(
                            f"Extracted to {output_dir} (flatten skipped: no matching subdirectory found)"
                        )
                else:
                    typer.echo(f"Extracted to {output_dir}")
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            dest = Path.cwd() / archive_name
            client.download(url_path, dest)
            typer.echo(f"Downloaded to {dest}")
    finally:
        client.close()


def models(
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", "-P", help="Filter by provider"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List available AI providers and available models."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        data = client.get_models()
    finally:
        client.close()

    providers = data.get("providers", [])
    default_provider = data.get("default_provider", "")
    default_model = data.get("default_model", "")
    available = data.get("available_models", {})

    if provider:
        if provider not in providers:
            typer.echo(f"Unknown provider: {provider}")
            raise typer.Exit(1)

    if json_output:
        if provider:
            filtered = {
                "providers": [provider],
                "default_provider": default_provider,
                "default_model": default_model,
                "available_models": {provider: available.get(provider, [])},
            }
            typer.echo(json.dumps(filtered, indent=2))
        else:
            typer.echo(json.dumps(data, indent=2))
        return

    if provider:
        providers = [provider]

    for p in providers:
        label = f"Provider: {p}"
        if p == default_provider:
            label += " (default)"
        typer.echo(label)

        models_list = available.get(p, [])
        if not models_list:
            typer.echo("  (no models available)")
        else:
            for entry in models_list:
                model_id = entry.get("id", "") if isinstance(entry, dict) else entry
                suffix = (
                    "  (default)"
                    if p == default_provider and model_id == default_model
                    else ""
                )
                typer.echo(f"  {model_id}{suffix}")
        typer.echo()
