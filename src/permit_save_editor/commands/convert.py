"""``ppse convert`` — ``.rjson`` ↔ ``.json`` round-trip."""

from __future__ import annotations

from pathlib import Path

import typer

from ..io import JSON_SUFFIX, RJSON_SUFFIX, is_obfuscated, load_save, save_save


def convert(
    path: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Source save file (.rjson or .json).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination path. Defaults to sibling with flipped extension.",
    ),
    no_backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Create a .bak before writing the new file (default: backup).",
    ),
) -> None:
    """Convert a save file. Auto-detects direction from the input extension."""
    save = load_save(path)

    if output is None:
        target_suffix = JSON_SUFFIX if is_obfuscated(path) else RJSON_SUFFIX
        output = path.with_suffix(target_suffix)

    save_save(save, output, backup=no_backup)
    typer.echo(f"Wrote {output}")
