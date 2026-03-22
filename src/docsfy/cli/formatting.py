from __future__ import annotations

import typer


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a formatted, column-aligned table to stdout.

    Column widths are computed automatically from the header and row contents.
    """
    num_cols = len(headers)
    # Pad or truncate rows to match header length
    normalized_rows = [
        row[:num_cols] + [""] * max(0, num_cols - len(row)) for row in rows
    ]
    all_rows = [headers, *normalized_rows]
    col_widths = [max(len(str(row[i])) for row in all_rows) for i in range(num_cols)]

    header_line = "  ".join(
        str(headers[i]).ljust(col_widths[i]) for i in range(num_cols)
    )
    typer.echo(header_line)
    typer.echo("  ".join("-" * w for w in col_widths))
    for row in normalized_rows:
        typer.echo("  ".join(str(row[i]).ljust(col_widths[i]) for i in range(num_cols)))
