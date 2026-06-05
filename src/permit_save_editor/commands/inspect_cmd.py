"""``ppse inspect`` — headless summary of a save file."""

from __future__ import annotations

from pathlib import Path

import typer

from ..io import is_obfuscated, load_save


def inspect(
    path: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to a .rjson or .json save file.",
    ),
) -> None:
    """Load the save and print key fields. No GUI required."""
    save = load_save(path)
    fmt = "rjson (cipher)" if is_obfuscated(path) else "json (plain)"

    typer.echo(f"File:        {path}")
    typer.echo(f"Format:      {fmt}")
    typer.echo("")
    typer.echo(f"Character:   {save.character_name!r}  (dog: {save.dog_name!r})")
    typer.echo(f"Gender:      {'female' if save.gender == 1 else 'male'}")
    typer.echo(f"Day:         {save.day_count}  (ID {save.day_id})")
    typer.echo(f"Play time:   {save.play_time:g} s")
    typer.echo(f"Story index: {save.story_timeline_index}")
    typer.echo("")
    typer.echo(f"Gold:   {save.gold:>7}")
    typer.echo(f"Wood:   {save.wood:>7}")
    typer.echo(f"Stone:  {save.stone:>7}")
    typer.echo(
        f"Rep:    {save.reputation:>7}  (trust {save.trust_point} / -{save.trust_penalty})"
    )
    typer.echo("")
    typer.echo(
        f"Levels: Badge={save.badge_level}  Carpenter={save.carpenter_level}  "
        f"Blacksmith={save.blacksmith_level}  Disease={save.disease_level}"
    )
    fishing = save.fish_exp_dict.values
    if len(fishing) >= 3:
        typer.echo(f"Fishing: {fishing[0]} / {fishing[1]} / {fishing[2]}")
    typer.echo("")
    typer.echo(
        f"Lock lists: skin={_count_unlocked(save.skin_lock_state_list)}  "
        f"hair={_count_unlocked(save.hair_lock_state_list)}  "
        f"cloth={_count_unlocked(save.cloth_lock_state_list)}  "
        f"cape={_count_unlocked(save.cape_lock_state_list)}"
    )
    typer.echo(
        f"Dict locks: fast-travel={save.fast_travel_state.all_enabled}  "
        f"recipes={save.recipe_lock_state.all_enabled}  "
        f"potions={save.potion_lock_state.all_enabled}"
    )
    sick = sum(1 for n in save.npc_health_data_list if n.is_sick)
    typer.echo(f"NPCs:      {len(save.npc_health_data_list)} ({sick} sick)")
    typer.echo(f"Rooms:     {len(save.room_editor_data)} objects placed")


def _count_unlocked(lock_list: list[bool]) -> str:
    if not lock_list:
        return "—"
    return f"{sum(lock_list)}/{len(lock_list)}"
