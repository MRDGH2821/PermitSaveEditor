"""Typer-based CLI for Permit Save Editor.

Single ``ppse`` entry point with subcommands:

* ``gui``     — launch the PySide6 GUI
* ``inspect`` — headless save-file summary
* ``convert`` — ``.rjson`` ↔ ``.json`` round-trip
* ``set``     — mutate individual fields
* ``unlock``  — bulk unlock flags (skins, recipes, ...)
* ``paths``   — print the default save directory
* ``version`` — print the package version
"""

from __future__ import annotations

from pathlib import Path

import typer

from . import __version__

app = typer.Typer(
    name="ppse",
    help="Potion Permit save editor (Python port of the WPF original).",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ppse {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Potion Permit save editor."""


# -- Subcommand registration --------------------------------------------------
# Each command module exposes a single function. We import the function and
# bind it to a subcommand name here. This is the cleanest pattern for
# multi-file typer CLIs — each subcommand is a first-class command, not a
# sub-Typer.
#
# We import the heavy ones (gui) lazily inside their command function so that
# `ppse inspect` doesn't pay the PySide6 import cost.

from .commands import convert, inspect_cmd, paths, set_cmd, unlock  # noqa: E402

app.command(name="convert")(convert.convert)
app.command(name="inspect")(inspect_cmd.inspect)
app.command(name="paths")(paths.show_paths)
app.command(name="set")(set_cmd.set_fields)
app.command(name="unlock")(unlock.unlock)


@app.command(name="gui")
def gui_cmd(
    path: Path | None = typer.Argument(
        None,
        exists=True,
        readable=True,
        help="Optional save file to open on startup.",
    ),
) -> None:
    """Launch the PySide6 save editor window."""
    from .commands import gui

    gui.run_gui(initial_path=path)
