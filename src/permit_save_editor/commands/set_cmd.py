"""``ppse set`` — mutate individual save fields from the command line."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..io import load_save, save_save
from ..models import Color


def _parse_color(value: str) -> Color:
    """Accept ``#RRGGBB`` or ``#AARRGGBB``."""
    v = value.lstrip("#")
    if len(v) == 6:
        r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
        return Color.from_qcolor(r, g, b, 255)
    if len(v) == 8:
        a, r, g, b = (
            int(v[0:2], 16),
            int(v[2:4], 16),
            int(v[4:6], 16),
            int(v[6:8], 16),
        )
        return Color.from_qcolor(r, g, b, a)
    raise typer.BadParameter(f"expected #RRGGBB or #AARRGGBB, got {value!r}")


def set_fields(
    path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Save file to mutate in-place."
    ),
    character_name: Annotated[str | None, typer.Option(help="Player name.")] = None,
    dog_name: Annotated[str | None, typer.Option(help="Dog's name.")] = None,
    gold: Annotated[int | None, typer.Option(help="Gold amount.", min=0, max=9999999)] = None,
    wood: Annotated[int | None, typer.Option(help="Wood amount.", min=0, max=9999999)] = None,
    stone: Annotated[int | None, typer.Option(help="Stone amount.", min=0, max=9999999)] = None,
    carpenter_level: Annotated[
        int | None, typer.Option(help="Carpenter level.", min=0, max=2)
    ] = None,
    blacksmith_level: Annotated[
        int | None, typer.Option(help="Blacksmith level.", min=0, max=2)
    ] = None,
    badge_level: Annotated[
        int | None, typer.Option(help="Badge level.", min=0, max=2)
    ] = None,
    gender: Annotated[
        int | None, typer.Option(help="0 = male, 1 = female.", min=0, max=1)
    ] = None,
    skin_color: Annotated[str | None, typer.Option(help="Skin color as #RRGGBB.")] = None,
    hair_color: Annotated[str | None, typer.Option(help="Hair color as #RRGGBB.")] = None,
    eyes_color: Annotated[str | None, typer.Option(help="Eye color as #RRGGBB.")] = None,
    cloth_color: Annotated[str | None, typer.Option(help="Outfit color as #RRGGBB.")] = None,
    cape_color: Annotated[str | None, typer.Option(help="Cape color as #RRGGBB.")] = None,
    no_backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Create a .bak before writing (default: backup).",
    ),
) -> None:
    """Edit one or more fields. The original is backed up to ``.bak`` first."""
    updates: list[tuple[str, object]] = []
    if character_name is not None:
        updates.append(("character_name", character_name))
    if dog_name is not None:
        updates.append(("dog_name", dog_name))
    if gold is not None:
        updates.append(("gold", gold))
    if wood is not None:
        updates.append(("wood", wood))
    if stone is not None:
        updates.append(("stone", stone))
    if carpenter_level is not None:
        updates.append(("carpenter_level", carpenter_level))
    if blacksmith_level is not None:
        updates.append(("blacksmith_level", blacksmith_level))
    if badge_level is not None:
        updates.append(("badge_level", badge_level))
    if gender is not None:
        updates.append(("gender", gender))
    for field, raw in (
        ("skin_color", skin_color),
        ("hair_color", hair_color),
        ("eyes_color", eyes_color),
        ("cloth_color", cloth_color),
        ("cape_color", cape_color),
    ):
        if raw is not None:
            updates.append((field, _parse_color(raw)))

    if not updates:
        typer.echo(
            "No fields specified. Use --help to see available options.", err=True
        )
        raise typer.Exit(code=2)

    save = load_save(path)
    for field, value in updates:
        setattr(save, field, value)
        typer.echo(f"  {field} = {value!r}")

    save_save(save, path, backup=no_backup)
    typer.echo(f"Wrote {path}" + ("" if no_backup else " (.bak created)"))
