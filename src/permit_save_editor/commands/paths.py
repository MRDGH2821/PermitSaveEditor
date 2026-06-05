"""``ppse paths`` — print the platform-appropriate default save directory."""

from __future__ import annotations

import typer

from ..paths import default_save_dir


def show_paths() -> None:
    """Print the default save directory (and create it if missing)."""
    typer.echo(str(default_save_dir()))
