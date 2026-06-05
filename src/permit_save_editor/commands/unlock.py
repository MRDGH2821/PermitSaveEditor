"""``ppse unlock`` — bulk-unlock flags in a save file."""

from __future__ import annotations

from pathlib import Path

import typer

from ..io import load_save, save_save


def unlock(
    path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Save file to mutate in-place."
    ),
    all_: bool = typer.Option(
        False,
        "--all",
        help="Unlock every category (skins, hair, clothes, capes, fast travel, recipes, potions).",
    ),
    skins: bool | None = typer.Option(
        None, "--skins", help="Unlock all skin styles."
    ),
    hair: bool | None = typer.Option(
        None, "--hair", help="Unlock all hair styles."
    ),
    clothes: bool | None = typer.Option(
        None, "--clothes", help="Unlock all outfits."
    ),
    capes: bool | None = typer.Option(
        None, "--capes", help="Unlock all capes."
    ),
    fast_travel: bool | None = typer.Option(
        None, "--fast-travel", help="Unlock all fast-travel points."
    ),
    recipes: bool | None = typer.Option(
        None, "--recipes", help="Unlock all recipes."
    ),
    potions: bool | None = typer.Option(
        None, "--potions", help="Unlock all potions."
    ),
    heal_npcs: bool = typer.Option(
        False, "--heal-npcs", help="Heal all NPCs (separate from unlocks)."
    ),
    no_backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Create a .bak before writing the new file (default: backup).",
    ),
) -> None:
    """Bulk-unlock the categories you select.

    Defaults to ``--all`` if no flags are given. This is an unlock-only
    command: every flag is opt-in. To *re-lock* a category, load the save in
    the GUI and uncheck the entries manually.
    """
    save = load_save(path)

    if all_ or all(
        v is None
        for v in (skins, hair, clothes, capes, fast_travel, recipes, potions)
    ):
        save.unlock_everything()
        for label in (
            "skins",
            "hair",
            "clothes",
            "capes",
            "fast_travel",
            "recipes",
            "potions",
        ):
            typer.echo(f"  unlocked {label}")
    else:
        if skins:
            for i in range(len(save.skin_lock_state_list)):
                save.skin_lock_state_list[i] = True
            typer.echo("  unlocked skins")
        if hair:
            for i in range(len(save.hair_lock_state_list)):
                save.hair_lock_state_list[i] = True
            typer.echo("  unlocked hair")
        if clothes:
            for i in range(len(save.cloth_lock_state_list)):
                save.cloth_lock_state_list[i] = True
            typer.echo("  unlocked clothes")
        if capes:
            for i in range(len(save.cape_lock_state_list)):
                save.cape_lock_state_list[i] = True
            typer.echo("  unlocked capes")
        if fast_travel:
            save.fast_travel_state.unlock_all()
            typer.echo("  unlocked fast travel")
        if recipes:
            save.recipe_lock_state.unlock_all()
            typer.echo("  unlocked recipes")
        if potions:
            save.potion_lock_state.unlock_all()
            typer.echo("  unlocked potions")

    if heal_npcs:
        save.heal_all_npcs()
        typer.echo("  healed all NPCs")

    save_save(save, path, backup=no_backup)
    typer.echo(f"Wrote {path}" + ("" if no_backup else " (.bak created)"))
