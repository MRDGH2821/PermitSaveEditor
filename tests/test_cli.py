"""Smoke tests for the CLI subcommands.

Each subcommand is invoked via typer's testing helpers; we don't actually
spawn a subprocess. The GUI subcommand is excluded — it's covered by
``test_gui.py`` under the ``offscreen`` Qt platform.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from permit_save_editor.cli import app

runner = CliRunner()


def test_help_shows_all_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("gui", "inspect", "convert", "set", "unlock", "paths"):
        assert cmd in result.stdout


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_paths_prints_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Override the home-relative path so the test is hermetic
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    result = runner.invoke(app, ["paths"])
    assert result.exit_code == 0
    assert str(tmp_path) in result.stdout


def test_inspect_prints_summary(sample_json_path: Path):
    result = runner.invoke(app, ["inspect", str(sample_json_path)])
    assert result.exit_code == 0
    assert "Logan" in result.stdout
    assert "Noxe" in result.stdout
    assert "Gold" in result.stdout
    assert "Carpenter" in result.stdout


def test_convert_rjson_to_json(sample_json_path: Path, tmp_path: Path):
    out = tmp_path / "converted.json"
    result = runner.invoke(app, ["convert", str(sample_json_path), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["characterName"] == "Logan"


def test_convert_json_to_rjson(sample_plain_path: Path, tmp_path: Path):
    out = tmp_path / "converted.rjson"
    result = runner.invoke(app, ["convert", str(sample_plain_path), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    # The on-disk rjson should be ciphered (no plain "Logan")
    assert "Logan" not in out.read_text(encoding="utf-8")


def test_set_updates_field(sample_json_path: Path):
    result = runner.invoke(
        app,
        [
            "set",
            str(sample_json_path),
            "--gold",
            "999999",
            "--character-name",
            "Mihir",
            "--no-backup",
        ],
    )
    assert result.exit_code == 0
    # Reload the file and confirm the changes
    from permit_save_editor.io import load_save

    reloaded = load_save(sample_json_path)
    assert reloaded.gold == 999999
    assert reloaded.character_name == "Mihir"


def test_set_with_no_fields_errors(sample_json_path: Path):
    result = runner.invoke(app, ["set", str(sample_json_path)])
    assert result.exit_code != 0


def test_set_color_accepts_hex(sample_json_path: Path):
    result = runner.invoke(
        app,
        [
            "set",
            str(sample_json_path),
            "--skin-color",
            "#ff8800",
            "--cape-color",
            "#80ff00ff",
            "--no-backup",
        ],
    )
    assert result.exit_code == 0
    from permit_save_editor.io import load_save

    reloaded = load_save(sample_json_path)
    assert reloaded.skin_color.r == pytest.approx(1.0, abs=1 / 255)
    assert reloaded.cape_color.a == pytest.approx(0.5, abs=1 / 255)


def test_set_color_invalid_format_errors(sample_json_path: Path):
    result = runner.invoke(
        app,
        ["set", str(sample_json_path), "--skin-color", "not-a-color"],
    )
    assert result.exit_code != 0


def test_unlock_all(sample_json_path: Path):
    result = runner.invoke(
        app, ["unlock", str(sample_json_path), "--all", "--no-backup"]
    )
    assert result.exit_code == 0
    from permit_save_editor.io import load_save

    reloaded = load_save(sample_json_path)
    assert all(reloaded.skin_lock_state_list)
    assert reloaded.fast_travel_state.all_enabled
    assert reloaded.recipe_lock_state.all_enabled
    assert reloaded.potion_lock_state.all_enabled


def test_unlock_specific_flags(sample_json_path: Path):
    result = runner.invoke(
        app,
        [
            "unlock",
            str(sample_json_path),
            "--skins",
            "--recipes",
            "--no-backup",
        ],
    )
    assert result.exit_code == 0
    from permit_save_editor.io import load_save

    reloaded = load_save(sample_json_path)
    assert all(reloaded.skin_lock_state_list)
    assert reloaded.recipe_lock_state.all_enabled
    # fast_travel_state should be untouched
    assert not reloaded.fast_travel_state.all_enabled


def test_unlock_heal_npcs(sample_json_path: Path):
    result = runner.invoke(
        app,
        [
            "unlock",
            str(sample_json_path),
            "--heal-npcs",
            "--no-backup",
        ],
    )
    assert result.exit_code == 0
    from permit_save_editor.io import load_save

    reloaded = load_save(sample_json_path)
    sick = sum(1 for n in reloaded.npc_health_data_list if n.is_sick)
    assert sick == 0
