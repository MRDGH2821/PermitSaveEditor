"""Shared pytest fixtures: a synthetic Potion Permit save and a tmp save dir."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from permit_save_editor.cipher import rot39
from permit_save_editor.models import GameSaveData

# A minimal-but-realistic save document. Covers the field types the editor
# actually exercises (booleans, ints, floats, lists, dicts, color objects).
SAMPLE_SAVE_DICT: dict = {
    "isEmptyData": False,
    "characterName": "Logan",
    "dogName": "Noxe",
    "dayCount": 14,
    "dayID": 14,
    "gold": 500,
    "wood": 250,
    "stone": 100,
    "reputation": 3,
    "canGainTrust": True,
    "trustPoint": 12,
    "trustPenalty": 0,
    "badgeLevel": 1,
    "diseaseLevel": 0,
    "blacksmithLevel": 0,
    "carpenterLevel": 1,
    "playTime": 12345.6,
    "gender": 0,
    "hairID": 0,
    "petDogieFP": 5,
    "storyTimelineIndex": 7,
    "partTimePoliceStationCount": 0,
    "partTimePostOfficeCount": 0,
    "partTimeChurchCount": 0,
    "isFirstDisease": False,
    "targetQuestID": 0,
    "diseaseDay": 0,
    "diseaseDayCounterSudden": 0,
    "diseaseCounter": 0,
    "skinColor": {"a": 1.0, "r": 0.9, "g": 0.7, "b": 0.6},
    "hairColor": {"a": 1.0, "r": 0.3, "g": 0.2, "b": 0.1},
    "eyesColor": {"a": 1.0, "r": 0.1, "g": 0.3, "b": 0.6},
    "clothColor": {"a": 1.0, "r": 0.5, "g": 0.5, "b": 0.5},
    "capeColor": {"a": 1.0, "r": 0.8, "g": 0.1, "b": 0.1},
    "skinLockStateList": [True, False, True, False],
    "hairLockStateList": [False, False, True],
    "eyesLockStateList": [True, True, True],
    "clothLockStateList": [False, False, False, False, False],
    "capeLockStateList": [False, True],
    "itemLockState": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "mapResourceState": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "fastTravelState": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": ["shop", "mine", "lake"],
        "_values": [True, False, True],
    },
    "potionLockState": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": ["potion_a", "potion_b"],
        "_values": [False, False],
    },
    "recipeLockState": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": ["recipe_a", "recipe_b", "recipe_c"],
        "_values": [True, False, False],
    },
    "tutorialFlag": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "triggerDiseaseDict": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "diseasePatternList": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "capsuleDict": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "upgradeDataDict": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "resourcesRecords": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "achievementDict": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": [],
        "_values": [],
    },
    "fishExpDict": {
        "reorderableList": None,
        "reqReferences": None,
        "isExpanded": False,
        "_keyValues": [],
        "_keys": ["rod1", "rod2", "rod3"],
        "_values": [10, 25, 75],
    },
    "keyItemActiveList": [],
    "researchList": [],
    "newMaterialList": [],
    "newFoodIDList": [],
    "newPotionIDList": [],
    "newFishIDList": [],
    "newNpcIDList": [],
    "newEnemyIDList": [],
    "newTutorialIDList": [],
    "newDiseaseDataList": [],
    "newQuestDataList": [],
    "eventStateData": [],
    "activeQuestList": [],
    "queueQuestList": [],
    "questProgressList": [],
    "npcFPDataList": [],
    "npcHealthDataList": [
        {"cureDelayCnt": 0, "isCure": True, "isSick": False, "npcHP": 10},
        {"cureDelayCnt": 3, "isCure": False, "isSick": True, "npcHP": 4},
    ],
    "roomEditorData": [
        {
            "roomObjectStr": "bed_basic",
            "roomObjectID": 1,
            "direction": 0,
            "position": {"x": 2, "y": 3},
        }
    ],
    "activeDiseaseList": [],
    "progressionObjDataList": [],
    "statusUpgradeList": [],
    "enemySlainDatas": [],
    "enemyQuestDatas": [],
    "fishRecordList": [],
    "campBedList": [],
    "playerInventoryItemData": [],
    "playerVendingData": [],
    "potionSaveData": [],
    "targetQuest": None,
}


@pytest.fixture
def sample_save() -> GameSaveData:
    """A populated ``GameSaveData`` for use in tests."""
    return GameSaveData.model_validate(SAMPLE_SAVE_DICT)


@pytest.fixture
def sample_json_path(tmp_path: Path) -> Path:
    """A .rjson save file (cipher-encoded) in a tmp dir."""
    out = tmp_path / "GameSave1.rjson"
    text = json.dumps(SAMPLE_SAVE_DICT, ensure_ascii=False)
    out.write_text(rot39(text), encoding="utf-8")
    return out


@pytest.fixture
def sample_plain_path(tmp_path: Path) -> Path:
    """A plain .json save file (no cipher) in a tmp dir."""
    out = tmp_path / "GameSave1.json"
    out.write_text(
        json.dumps(SAMPLE_SAVE_DICT, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


@pytest.fixture
def sample_quests_dict() -> list[dict]:
    """Three active quests covering: partial completion, all-incomplete, no-reqs."""
    return [
        {
            "npcID": "npc_mayor",
            "questState": "InProgress",
            "questGiverName": "Mayor",
            "questID": "quest_intro",
            "questName": "Welcome to Moon Brook",
            "questActive": True,
            "questRequirementCheckerList": [
                {"complete": True},
                {"complete": False},
                {"complete": False},
            ],
        },
        {
            "npcID": "npc_healer",
            "questState": "InProgress",
            "questGiverName": "Healer",
            "questID": "quest_heal",
            "questName": "Patient Care",
            "questActive": True,
            "questRequirementCheckerList": [
                {"complete": False},
                {"complete": False},
            ],
        },
        {
            "npcID": "npc_blacksmith",
            "questState": "ReadyToTurnIn",
            "questGiverName": "Blacksmith",
            "questID": "quest_free",
            "questName": "Open Contract",
            "questActive": True,
            "questRequirementCheckerList": [],
        },
    ]


@pytest.fixture
def sample_json_path_with_quests(tmp_path: Path, sample_quests_dict) -> Path:
    """A .rjson save file populated with the sample_quests_dict."""
    from copy import deepcopy

    data = {**SAMPLE_SAVE_DICT, "activeQuestList": deepcopy(sample_quests_dict)}
    out = tmp_path / "GameSaveQuests.rjson"
    text = json.dumps(data, ensure_ascii=False)
    out.write_text(rot39(text), encoding="utf-8")
    return out


@pytest.fixture
def save_via_io(sample_json_path: Path) -> GameSaveData:
    """Load a save through the public IO layer (round-trip smoke test)."""
    from permit_save_editor.io import load_save

    return load_save(sample_json_path)
