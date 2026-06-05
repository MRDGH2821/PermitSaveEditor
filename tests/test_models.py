"""Tests for the pydantic data models."""

from __future__ import annotations

import pytest

from permit_save_editor.models import (
    Color,
    GameSaveData,
    NpcHealthData,
    RoomEditorData,
    SerializedDict,
)


def test_blank_save_has_sensible_defaults():
    """A fresh ``GameSaveData()`` mirrors the C# parameterless ctor."""
    s = GameSaveData()
    assert s.character_name == "Logan"
    assert s.dog_name == "Noxe"
    assert s.gold == 500
    assert s.gender == 0
    assert s.fish_exp_dict.values == []
    # Color objects should default to white, not crash
    assert s.skin_color == Color(a=1.0, r=1.0, g=1.0, b=1.0)


def test_sample_save_validates(sample_save: GameSaveData) -> None:
    """The fixture save loads cleanly."""
    assert sample_save.character_name == "Logan"
    assert sample_save.gold == 500
    assert len(sample_save.npc_health_data_list) == 2
    assert sample_save.room_editor_data[0].position.x == 2


def test_round_trip_preserves_all_fields(sample_save: GameSaveData) -> None:
    """model_dump(by_alias=True) must round-trip back into an equal model."""
    dumped = sample_save.model_dump(by_alias=True)
    reloaded = GameSaveData.model_validate(dumped)
    assert reloaded == sample_save


def test_snake_case_python_field_names_map_to_camelcase_json_keys():
    """populate_by_name=True lets us construct from snake_case Python names."""
    s = GameSaveData.model_validate(
        {
            "characterName": "Test",
            "isFirstDisease": True,
            "fishExpDict": {
                "_keys": ["a"],
                "_values": [1],
            },
        }
    )
    # Constructed via camelCase aliases
    assert s.character_name == "Test"
    assert s.is_first_disease is True
    assert s.fish_exp_dict.values == [1]
    # And via snake_case Python names too
    s2 = GameSaveData.model_validate(
        {
            "character_name": "Test",
            "is_first_disease": False,
        }
    )
    assert s2.character_name == "Test"
    assert s2.is_first_disease is False


def test_id_suffix_fields_use_uppercase_id():
    """Fields like `npcID`, `dayID`, `targetQuestID` keep the `ID` uppercased.

    Pydantic's `to_camel` alias generator lowercases the second char of an
    acronym; we override with explicit Field aliases to match the game's
    JSON convention.
    """
    s = GameSaveData(
        hair_id=7,  # Python snake -> JSON "hairID"
        day_id=14,  # -> "dayID"
        target_quest_id=99,  # -> "targetQuestID"
    )
    dumped = s.model_dump(by_alias=True)
    assert "hairID" in dumped
    assert "dayID" in dumped
    assert "targetQuestID" in dumped
    assert dumped["hairID"] == 7


def test_underscore_prefixed_aliases():
    """The Unity dict pattern uses `_keys` / `_values` / `_keyValues`."""
    sd = SerializedDict.model_validate(
        {
            "_keys": ["a", "b"],
            "_values": [True, False],
            "_keyValues": ["a=True", "b=False"],
        }
    )
    assert sd.keys == ["a", "b"]
    assert sd.values == [True, False]
    assert sd.key_values == ["a=True", "b=False"]
    dumped = sd.model_dump(by_alias=True)
    assert dumped["_keys"] == ["a", "b"]


def test_color_to_qcolor_round_trip():
    """Color (0.0-1.0) <-> 0-255 ints."""
    c = Color(r=0.5, g=0.25, b=0.0, a=1.0)
    r, g, b, a = c.to_qcolor()
    assert (r, g, b, a) == (128, 64, 0, 255)
    back = Color.from_qcolor(r, g, b, a)
    assert back.r == pytest.approx(c.r, abs=1 / 255)
    assert back.g == pytest.approx(c.g, abs=1 / 255)


def test_npc_heal_resets_to_healthy():
    npc = NpcHealthData(cure_delay_cnt=5, is_cure=False, is_sick=True, npc_hp=2)
    npc.heal()
    assert npc.cure_delay_cnt == 0
    assert npc.is_cure is False
    assert npc.is_sick is False
    assert npc.npc_hp == 10


def test_unlock_everything_sets_all_lock_lists_true(sample_save: GameSaveData):
    """The eight unlock buttons collapse to one model method."""
    # Pre-condition: at least one lock list is not all-True
    assert not all(sample_save.skin_lock_state_list)
    assert not all(sample_save.hair_lock_state_list)
    assert not sample_save.fast_travel_state.all_enabled
    assert not sample_save.recipe_lock_state.all_enabled
    assert not sample_save.potion_lock_state.all_enabled

    sample_save.unlock_everything()

    assert all(sample_save.skin_lock_state_list)
    assert all(sample_save.hair_lock_state_list)
    assert all(sample_save.eyes_lock_state_list)
    assert all(sample_save.cloth_lock_state_list)
    assert all(sample_save.cape_lock_state_list)
    assert sample_save.fast_travel_state.all_enabled
    assert sample_save.recipe_lock_state.all_enabled
    assert sample_save.potion_lock_state.all_enabled


def test_heal_all_npcs_resets_health(sample_save: GameSaveData):
    sick_before = sum(1 for n in sample_save.npc_health_data_list if n.is_sick)
    assert sick_before == 1
    sample_save.heal_all_npcs()
    sick_after = sum(1 for n in sample_save.npc_health_data_list if n.is_sick)
    assert sick_after == 0
    assert all(n.npc_hp == 10 for n in sample_save.npc_health_data_list)


def test_extra_fields_are_ignored():
    """Unknown JSON keys are silently dropped (the game may add new fields)."""
    s = GameSaveData.model_validate(
        {
            "characterName": "X",
            "thisFieldDoesNotExist": "whatever",
            "anotherNewField": [1, 2, 3],
        }
    )
    assert s.character_name == "X"
    # Pydantic's `extra="ignore"` means no error and no attribute


def test_room_editor_data_default_position():
    """A RoomEditorData with no position defaults to (0, 0)."""
    r = RoomEditorData()
    assert r.position.x == 0
    assert r.position.y == 0


def test_int_keyed_serialized_dict_validates():
    """Unity's int-keyed dicts (capsuleDict, upgradeDataDict, …) use
    integer parallel-array keys. The model must accept those.

    Regression for the GUI error:
      capsuleDict._keys.0 — Input should be a valid string, input_value=1
    """
    s = GameSaveData.model_validate(
        {
            "characterName": "X",
            "capsuleDict": {
                "_keys": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
                "_values": [
                    True, False, True, False, True, False,
                    True, False, True, False, True,
                ],
                "_keyValues": [],
            },
            "upgradeDataDict": {
                "_keys": [100, 200, 300],
                "_values": [0, 5, 12],
                "_keyValues": [],
            },
            "diseasePatternList": {
                "_keys": [0, 1, 2],
                "_values": [True, True, False],
                "_keyValues": [],
            },
        }
    )
    assert s.capsule_dict.keys == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    assert s.upgrade_data_dict.keys == [100, 200, 300]
    assert s.disease_pattern_list.keys == [0, 1, 2]


def test_serialized_dict_round_trips_int_keys():
    """Int keys must survive a model_dump → model_validate round-trip."""
    payload = {
        "characterName": "X",
        "capsuleDict": {
            "_keys": [1, 2, 3],
            "_values": [True, False, True],
            "_keyValues": [],
        },
    }
    s1 = GameSaveData.model_validate(payload)
    dumped = s1.model_dump(by_alias=True)
    s2 = GameSaveData.model_validate(dumped)
    assert s2.capsule_dict.keys == [1, 2, 3]
    assert s2.capsule_dict.values == [True, False, True]
