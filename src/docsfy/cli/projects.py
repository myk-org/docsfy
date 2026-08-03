from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

from docsfy.cli.formatting import print_table
from docsfy.models import encode_branch_for_path, is_uuid

# Exact paths that must never be cleared (descendants of these are allowed).
_UNSAFE_CLEAR_EXACT: frozenset[Path] = frozenset(
    {
        Path("/"),
        Path("/home"),
        Path("/Users"),  # macOS home root (descendants allowed)
        Path("/opt"),
        Path("/tmp"),
        Path("/var/tmp"),
    }
)

# Refuse these trees and all descendants (see /var/tmp exception below).
_UNSAFE_CLEAR_PREFIXES: frozenset[Path] = frozenset(
    {
        Path("/etc"),
        Path("/usr"),
        Path("/boot"),
        Path("/root"),
        Path("/dev"),
        Path("/proc"),
        Path("/sys"),
        Path("/run"),
        Path("/var"),
        Path("/System"),  # macOS system tree
        Path("/Library"),  # macOS system library tree
    }
)

_VAR_TMP = Path("/var/tmp")


def _path_is_or_under(path: Path, root: Path) -> bool:
    """Return True if *path* is *root* or a descendant of *root*."""
    return path == root or root in path.parents


def _refuse_unsafe_clear_target(directory: Path) -> None:
    """Raise Exit(1) if *directory* must not have its contents replaced.

    Refuses filesystem / common system roots (exact), sensitive system trees
    and their descendants (``/etc``, ``/usr``, ``/var``, … — except
    ``/var/tmp/...`` descendants), the user's home directory, the current
    working directory, ancestors of cwd, and symlink paths (including
    dangling symlinks).
    """
    expanded = directory.expanduser()
    if expanded.is_symlink():
        typer.echo(f"Refusing to clear symlink path: {expanded}", err=True)
        raise typer.Exit(code=1)

    resolved = expanded.resolve()
    cwd_resolved = Path.cwd().resolve()
    unsafe_exact = {p.resolve() for p in _UNSAFE_CLEAR_EXACT}
    unsafe_exact.add(Path.home().resolve())
    unsafe_exact.add(cwd_resolved)
    # Refuse ancestors of cwd (e.g. ``-o ..``) so parent trees are never wiped.
    unsafe_exact.update(cwd_resolved.parents)
    if resolved in unsafe_exact:
        typer.echo(f"Refusing to clear dangerous path: {resolved}", err=True)
        raise typer.Exit(code=1)

    var_resolved = Path("/var").resolve()
    var_tmp_resolved = _VAR_TMP.resolve()
    for prefix in _UNSAFE_CLEAR_PREFIXES:
        root = prefix.resolve()
        if not _path_is_or_under(resolved, root):
            continue
        # Allow descendants of /var/tmp (exact /var/tmp is refused above).
        if (
            root == var_resolved
            and _path_is_or_under(resolved, var_tmp_resolved)
            and resolved != var_tmp_resolved
        ):
            continue
        typer.echo(f"Refusing to clear dangerous path: {resolved}", err=True)
        raise typer.Exit(code=1)


def _move_directory_entries(src: Path, dest: Path) -> None:
    """Move all entries from *src* into *dest* (dest must exist).

    If a same-named entry already exists under *dest*, remove it first so the
    move replaces rather than nesting (``dest/name/name``).

    Rejects *src* that is a symlink or not a real directory (lstat semantics)
    so a TOCTOU swap to a symlink cannot redirect the move.
    """
    # lstat: is_symlink() / is_dir(follow_symlinks=False) must not follow links.
    if src.is_symlink() or not src.is_dir(follow_symlinks=False):
        raise OSError(f"Refusing to move from non-directory or symlink path: {src}")
    for item in list(src.iterdir()):
        dest_path = dest / item.name
        if dest_path.exists() or dest_path.is_symlink():
            if dest_path.is_dir() and not dest_path.is_symlink():
                shutil.rmtree(dest_path)
            else:
                dest_path.unlink()
        shutil.move(str(item), str(dest_path))


def _clear_directory_entries(directory: Path) -> None:
    """Remove all entries under *directory*, keeping the directory itself.

    Symlink directory entries are unlinked (not followed). Caller must have
    already validated *directory* via ``_refuse_unsafe_clear_target``.
    """
    # Re-check immediately before iterating (TOCTOU: path may have become a symlink).
    if directory.is_symlink() or not directory.is_dir(follow_symlinks=False):
        return
    for item in directory.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()


def _warn_unrecovered_aside(aside: Path) -> None:
    """Remove empty *aside* or warn if files remain."""
    try:
        aside.rmdir()
    except OSError:
        typer.echo(
            f"Warning: left unrecovered aside directory at {aside}",
            err=True,
        )


def _partial_recover_aside(output_dir: Path, aside: Path) -> None:
    """Move aside entries back only where the destination is missing."""
    if not aside.exists():
        return
    for item in list(aside.iterdir()):
        dest = output_dir / item.name
        if not dest.exists() and not dest.is_symlink():
            shutil.move(str(item), str(dest))
    _warn_unrecovered_aside(aside)


def _restore_aside_to_output(output_dir: Path, aside: Path) -> None:
    """Clear *output_dir* and move all aside entries back."""
    _clear_directory_entries(output_dir)
    _move_directory_entries(aside, output_dir)
    _warn_unrecovered_aside(aside)


def _replace_directory_contents(output_dir: Path, source_dir: Path) -> None:
    """Replace contents of *output_dir* with contents of *source_dir*.

    Moves existing output aside first, installs the new tree, then deletes the
    aside on success. On install failure or interrupt, restores the aside so
    existing output is left intact. Download/extract failures never call this
    and leave output untouched.

    Unsafe-path checks (``typer.Exit``) run before the aside window so they are
    not treated as install failures.
    """
    _refuse_unsafe_clear_target(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Re-check after mkdir in case a symlink appeared at the path.
    _refuse_unsafe_clear_target(output_dir)

    aside = Path(tempfile.mkdtemp(prefix=".docsfy-aside-", dir=str(output_dir.parent)))
    moved_aside = False
    try:
        # Re-check immediately before moving output aside (TOCTOU).
        _refuse_unsafe_clear_target(output_dir)
        _move_directory_entries(output_dir, aside)
        moved_aside = True
        _move_directory_entries(source_dir, output_dir)
    except BaseException:
        if moved_aside:
            try:
                _restore_aside_to_output(output_dir, aside)
            except BaseException:
                _partial_recover_aside(output_dir, aside)
                raise
        else:
            _partial_recover_aside(output_dir, aside)
        raise
    else:
        try:
            shutil.rmtree(aside)
        except OSError:
            _warn_unrecovered_aside(aside)


def _flatten_extracted_tree(
    root: Path,
    expected_name: str,
) -> bool:
    """Flatten a single nested docs directory into *root*.

    Returns True if a nested directory was found and flattened.
    """
    expected_dir = root / expected_name
    nested_dir: Path | None = None
    if expected_dir.is_dir():
        nested_dir = expected_dir
    else:
        subdirs = [
            d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
        if len(subdirs) == 1:
            nested_dir = subdirs[0]
    if nested_dir is None:
        return False

    _move_directory_entries(nested_dir, root)
    nested_dir.rmdir()
    return True


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
    status_filter: str | None = typer.Option(
        None, "--status", help="Filter by status (ready, generating, error)"
    ),
    provider_filter: str | None = typer.Option(
        None, "--provider", help="Filter by AI provider"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
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
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Filter by provider"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Filter by model"),
    owner: str | None = typer.Option(
        None, "--owner", help="Project owner (for admin disambiguation)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
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
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),
    branch: str | None = typer.Option(
        None, "--branch", "-b", help="Branch of variant to delete"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Provider of variant to delete"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model of variant to delete"
    ),
    owner: str | None = typer.Option(
        None, "--owner", help="Project owner (required for admin)"
    ),
    all_variants: bool = typer.Option(
        False, "--all", help="Delete all variants of the project"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
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
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),
    branch: str | None = typer.Option(
        None, "--branch", "-b", help="Branch of variant to abort"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Provider of variant to abort"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model of variant to abort"
    ),
    owner: str | None = typer.Option(
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
    name: str = typer.Argument(help="Project name or generation ID (UUID)"),
    branch: str | None = typer.Option(
        None, "--branch", "-b", help="Branch of variant to download"
    ),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Provider of variant to download"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model of variant to download"
    ),
    owner: str | None = typer.Option(
        None, "--owner", help="Project owner (for admin disambiguation)"
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            "Output directory to extract to (replaces existing contents after a "
            "successful download and extract; default: save tar.gz to current dir)"
        ),
    ),
    flatten: bool = typer.Option(
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
            # Path segment must use encoded branch (matches server URL + tar arcname).
            safe_branch = encode_branch_for_path(branch)
            nested_archive_dir = f"{name}-{safe_branch}-{provider}-{model}"
            url_path = (
                f"/api/projects/{name}/{safe_branch}/{provider}/{model}/download"
                f"{owner_qs}"
            )
            archive_name = f"{nested_archive_dir}-docs.tar.gz"
        else:
            nested_archive_dir = name
            url_path = f"/api/projects/{name}/download{owner_qs}"
            archive_name = f"{name}-docs.tar.gz"

        if output:
            output_dir = Path(output).expanduser()
            # Fail fast before download so dangerous targets never touch the network.
            _refuse_unsafe_clear_target(output_dir)

            # Download + extract into a staging tree first. Existing output is only
            # replaced after staging succeeds; install failures restore prior contents.
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            extract_dir: Path | None = None

            try:
                client.download(url_path, tmp_path)
                extract_dir = Path(tempfile.mkdtemp(prefix="docsfy-download-"))
                with tarfile.open(tmp_path, "r:gz") as tar:
                    tar.extractall(path=extract_dir, filter="data")

                flattened = False
                if flatten:
                    # Tar top-level dir uses encode_branch_for_path (server arcname).
                    flattened = _flatten_extracted_tree(extract_dir, nested_archive_dir)

                _replace_directory_contents(output_dir, extract_dir)
                if flatten and flattened:
                    typer.echo(f"Extracted and flattened to {output_dir}")
                elif flatten:
                    typer.echo(
                        f"Extracted to {output_dir} "
                        "(flatten skipped: no matching subdirectory found)"
                    )
                else:
                    typer.echo(f"Extracted to {output_dir}")
            finally:
                tmp_path.unlink(missing_ok=True)
                if extract_dir is not None:
                    shutil.rmtree(extract_dir, ignore_errors=True)
        else:
            dest = Path.cwd() / archive_name
            client.download(url_path, dest)
            typer.echo(f"Downloaded to {dest}")
    finally:
        client.close()


def models(
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-P", help="Filter by provider"),
    ] = None,
    refresh: Annotated[
        bool,
        typer.Option("--refresh", "-r", help="Refresh models from AI providers"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List available AI providers and available models."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        if refresh:
            data = client.refresh_models()
            if not json_output:
                typer.echo("Models refreshed from AI providers.\n")
        else:
            data = client.get_models()
    finally:
        client.close()

    providers = data.get("providers", [])
    default_provider = data.get("default_provider", "")
    default_model = data.get("default_model", "")
    available = data.get("available_models", {})

    if provider and provider not in providers:
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
