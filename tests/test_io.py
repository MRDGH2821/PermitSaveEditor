"""Tests for the IO layer (load/save round-trip, .bak backup, format detection)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from permit_save_editor.cipher import rot39
from permit_save_editor.io import (
    dump_plain_json,
    is_obfuscated,
    load_save,
    save_save,
)
from permit_save_editor.models import GameSaveData


def test_load_rjson_returns_save(sample_json_path: Path) -> None:
    save = load_save(sample_json_path)
    assert isinstance(save, GameSaveData)
    assert save.character_name == "Logan"


def test_load_plain_json_returns_save(sample_plain_path: Path) -> None:
    save = load_save(sample_plain_path)
    assert isinstance(save, GameSaveData)
    assert save.character_name == "Logan"


def test_load_invalid_raises_value_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.rjson"
    # Write something that decrypts to invalid JSON
    bad.write_text(rot39("not json {{{"), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_save(bad)


def test_save_rjson_round_trip(sample_save: GameSaveData, tmp_path: Path) -> None:
    out = tmp_path / "round.rjson"
    save_save(sample_save, out)
    assert out.exists()
    # The on-disk file should be ciphered (no plain "Logan" substring)
    raw = out.read_text(encoding="utf-8")
    assert "Logan" not in raw
    # And the deciphered content should match the original model
    reloaded = load_save(out)
    assert reloaded == sample_save


def test_save_plain_json_round_trip(sample_save: GameSaveData, tmp_path: Path) -> None:
    out = tmp_path / "round.json"
    save_save(sample_save, out)
    raw = out.read_text(encoding="utf-8")
    # Plain JSON contains the unciphered "Logan" string
    assert "Logan" in raw
    reloaded = load_save(out)
    assert reloaded == sample_save


def test_save_obfuscate_true_writes_ciphered(sample_save: GameSaveData, tmp_path: Path) -> None:
    out = tmp_path / "x.json"
    save_save(sample_save, out, obfuscate=True)
    # Even though the extension is .json, explicit obfuscate=True wins
    raw = out.read_text(encoding="utf-8")
    assert "Logan" not in raw


def test_save_obfuscate_false_writes_plain(sample_save: GameSaveData, tmp_path: Path) -> None:
    out = tmp_path / "x.rjson"
    save_save(sample_save, out, obfuscate=False)
    raw = out.read_text(encoding="utf-8")
    assert "Logan" in raw


def test_bak_backup_renames_existing_file(sample_save: GameSaveData, tmp_path: Path) -> None:
    """Saving over an existing file should move the original to .bak first."""
    out = tmp_path / "GameSave1.rjson"
    # Seed with a marker so we can verify the backup contains the original
    out.write_text("ORIGINAL_MARKER", encoding="utf-8")
    save_save(sample_save, out, backup=True)
    bak = out.with_name(out.name + ".bak")
    assert bak.exists()
    assert bak.read_text(encoding="utf-8") == "ORIGINAL_MARKER"
    # The new file should be the freshly written save
    reloaded = load_save(out)
    assert reloaded == sample_save


def test_bak_not_overwritten_on_repeat_save(sample_save: GameSaveData, tmp_path: Path) -> None:
    """A second save should NOT clobber the original .bak."""
    out = tmp_path / "GameSave1.rjson"
    out.write_text("FIRST_ORIGINAL", encoding="utf-8")
    save_save(sample_save, out, backup=True)
    bak = out.with_name(out.name + ".bak")
    first_bak = bak.read_text(encoding="utf-8")
    # Second save: should not re-backup (bak already exists)
    out.write_text("SECOND_ORIGINAL", encoding="utf-8")
    save_save(sample_save, out, backup=True)
    assert bak.read_text(encoding="utf-8") == first_bak
    # A new .bak2 (or similar) is NOT created — we preserve the original bak
    assert not (out.with_name(out.name + ".bak2")).exists()


def test_no_backup_skips_bak(sample_save: GameSaveData, tmp_path: Path) -> None:
    out = tmp_path / "GameSave1.rjson"
    out.write_text("ORIGINAL", encoding="utf-8")
    save_save(sample_save, out, backup=False)
    assert not (out.with_name(out.name + ".bak")).exists()
    reloaded = load_save(out)
    assert reloaded == sample_save


def test_dump_plain_json_does_not_create_bak(sample_save: GameSaveData, tmp_path: Path) -> None:
    out = tmp_path / "GameSave1.json"
    dump_plain_json(sample_save, out)
    assert out.exists()
    # No backup behavior — this is an export
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["characterName"] == "Logan"


def test_is_obfuscated_helper() -> None:
    assert is_obfuscated(Path("a.rjson"))
    assert not is_obfuscated(Path("a.json"))
    # Case-insensitive
    assert is_obfuscated(Path("A.RJSON"))


def test_save_path_no_extension_is_obfuscated_by_default(
    sample_save: GameSaveData, tmp_path: Path
) -> None:
    """Files without an extension are treated as obfuscated (game-native)."""
    out = tmp_path / "GameSave1"
    save_save(sample_save, out)
    raw = out.read_text(encoding="utf-8")
    assert "Logan" not in raw  # ciphered
