"""Unit tests for :mod:`permit_save_editor.quest_progress`.

The helper module is the per-sub-task "complete" / "incomplete" logic
that backs the Quests tab. It operates on the raw quest dicts inside
``GameSaveData.active_quest_list`` and must mutate them in place, since
the GUI keeps references to those same dicts.
"""

from __future__ import annotations

import pytest

from permit_save_editor.quest_progress import (
    mark_subtask_complete,
    mark_subtask_incomplete,
)

# -- KILL_MONSTERS --------------------------------------------------------


def test_kill_monsters_complete_bumps_current_count_to_target() -> None:
    """KILL sub-task: CURRENT_KILL_MONSTER[].count should match TARGET."""
    quest = {
        "questReqType": "KILL_MONSTERS",
        "questKillReq": {
            "CURRENT_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 2}],
            "TARGET_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 5}],
        },
    }
    checker = {"complete": False, "requirementText": "Defeat Blackpaw (2/5)"}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert checker["complete"] is True
    assert quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 5


def test_kill_monsters_multiple_subtasks_bumped_independently() -> None:
    """Marking sub-task 0 complete must NOT bump sub-task 1's CURRENT count."""
    quest = {
        "questReqType": "KILL_MONSTERS",
        "questKillReq": {
            "CURRENT_KILL_MONSTER": [
                {"monster": "A", "count": 1},
                {"monster": "B", "count": 0},
            ],
            "TARGET_KILL_MONSTER": [
                {"monster": "A", "count": 3},
                {"monster": "B", "count": 7},
            ],
        },
    }
    checkers = [
        {"complete": False, "requirementText": "A"},
        {"complete": False, "requirementText": "B"},
    ]
    # Mark only the first sub-task complete
    mark_subtask_complete(checkers[0], quest, sub_task_index=0)
    assert quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 3
    # The second sub-task's CURRENT count must be untouched
    assert quest["questKillReq"]["CURRENT_KILL_MONSTER"][1]["count"] == 0


# -- COLLECT_ITEMS --------------------------------------------------------


def test_collect_items_complete_only_flips_flag() -> None:
    """COLLECT has no CURRENT to bump — checker is the only thing that moves."""
    quest = {
        "questReqType": "COLLECT_ITEMS",
        "questCollectReq": {
            "TARGET_COLLECT_ITEM": [{"item": "X", "count": 5}],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert checker["complete"] is True
    # questCollectReq has no CURRENT — nothing should have been added
    assert "CURRENT_COLLECT_ITEM" not in quest["questCollectReq"]


# -- TALK_WITH_NPC --------------------------------------------------------


def test_talk_with_npc_complete_bumps_current_count() -> None:
    """TALK sub-task: CURRENT_TALK_WITH_NPC[].count should match TARGET."""
    quest = {
        "questReqType": "TALK_WITH_NPC",
        "questTalkReq": {
            "CURRENT_TALK_WITH_NPC": [{"npc": "DERREK", "count": 0}],
            "TARGET_TALK_WITH_NPC": [{"npc": "DERREK", "count": 1}],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert checker["complete"] is True
    assert quest["questTalkReq"]["CURRENT_TALK_WITH_NPC"][0]["count"] == 1


# -- TRIGGER_EVENT --------------------------------------------------------


def test_trigger_event_complete_sets_triggered_true() -> None:
    """TRIGGER_EVENT sub-task: CURRENT[].triggered should be True."""
    quest = {
        "questReqType": "TRIGGER_EVENT",
        "questEventReq": {
            "CURRENT_EVENT_TRIGGERED": [{"eventID": "X", "triggered": False}],
            "TARGET_EVENT_TRIGGERED": [{"eventID": "X", "triggered": False}],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert quest["questEventReq"]["CURRENT_EVENT_TRIGGERED"][0]["triggered"] is True


def test_trigger_event_complete_only_flips_targeted_index() -> None:
    """Multiple TRIGGER_EVENT sub-tasks: only the indexed one flips."""
    quest = {
        "questReqType": "TRIGGER_EVENT",
        "questEventReq": {
            "CURRENT_EVENT_TRIGGERED": [
                {"eventID": "A", "triggered": False},
                {"eventID": "B", "triggered": False},
            ],
            "TARGET_EVENT_TRIGGERED": [
                {"eventID": "A", "triggered": False},
                {"eventID": "B", "triggered": False},
            ],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=1)
    assert quest["questEventReq"]["CURRENT_EVENT_TRIGGERED"][0]["triggered"] is False
    assert quest["questEventReq"]["CURRENT_EVENT_TRIGGERED"][1]["triggered"] is True


# -- ITEM_DELIVERY --------------------------------------------------------


def test_item_delivery_complete_bumps_current_count() -> None:
    """DELIVERY sub-task: CURRENT_DELIVERY[].count should match TARGET."""
    quest = {
        "questReqType": "ITEM_DELIVERY",
        "questDeliveryReq": {
            "CURRENT_DELIVERY": [{"item": "X", "count": 0}],
            "TARGET_DELIVERY": [{"item": "X", "count": 1}],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert quest["questDeliveryReq"]["CURRENT_DELIVERY"][0]["count"] == 1


# -- PROGRESS -------------------------------------------------------------


def test_progress_complete_copies_all_scalars() -> None:
    """PROGRESS: every CURRENT_X scalar gets set to TARGET_X (index ignored)."""
    quest = {
        "questReqType": "PROGRESS",
        "questProgressReq": {
            "CURRENT_FP_COUNT": 0,
            "CURRENT_TOWN_UPGRADE_COUNT": 1,
            "TARGET_FP_COUNT": 5,
            "TARGET_TOWN_UPGRADE_COUNT": 3,
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert quest["questProgressReq"]["CURRENT_FP_COUNT"] == 5
    assert quest["questProgressReq"]["CURRENT_TOWN_UPGRADE_COUNT"] == 3


def test_progress_complete_skips_non_numeric_fields() -> None:
    """Non-numeric CURRENT_X fields (e.g. strings) are left alone."""
    quest = {
        "questReqType": "PROGRESS",
        "questProgressReq": {
            "CURRENT_EVENT_TAG": "nope",
            "TARGET_EVENT_TAG": "yep",
            "CURRENT_FP_COUNT": 0,
            "TARGET_FP_COUNT": 5,
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    # Numeric field was bumped
    assert quest["questProgressReq"]["CURRENT_FP_COUNT"] == 5
    # String field was NOT touched
    assert quest["questProgressReq"]["CURRENT_EVENT_TAG"] == "nope"


# -- incomplete -----------------------------------------------------------


def test_incomplete_only_flips_flag() -> None:
    """Incomplete must not touch CURRENT values."""
    quest = {
        "questReqType": "KILL_MONSTERS",
        "questKillReq": {
            "CURRENT_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 5}],
            "TARGET_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 5}],
        },
    }
    checker = {"complete": True}
    mark_subtask_incomplete(checker)
    assert checker["complete"] is False
    # CURRENT value preserved
    assert quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 5


# -- safety / robustness --------------------------------------------------


@pytest.mark.parametrize(
    "checker",
    ["not a dict", None, 42, ["list", "not", "dict"]],
    ids=["str", "none", "int", "list"],
)
def test_incomplete_is_safe_on_non_dict_checker(checker) -> None:
    """A malformed checker (not a dict) must not crash the handler."""
    mark_subtask_incomplete(checker)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "checker",
    ["not a dict", None, 42],
    ids=["str", "none", "int"],
)
def test_complete_is_safe_on_non_dict_checker(checker) -> None:
    """Same defensive contract for ``mark_subtask_complete``."""
    mark_subtask_complete(
        checker,  # type: ignore[arg-type]
        {"questReqType": "KILL_MONSTERS"},
        sub_task_index=0,
    )


def test_complete_is_safe_when_req_dict_is_missing() -> None:
    """A quest with no questKillReq/etc. should still flip the flag cleanly."""
    quest = {"questReqType": "KILL_MONSTERS"}
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert checker["complete"] is True


def test_complete_handles_unknown_req_type_gracefully() -> None:
    """An unknown questReqType should not crash — just flip the flag."""
    quest = {"questReqType": "SOMETHING_NEW_FROM_A_FUTURE_PATCH"}
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=0)
    assert checker["complete"] is True


def test_complete_ignores_out_of_range_index() -> None:
    """An index past the end of the CURRENT list is silently ignored."""
    quest = {
        "questReqType": "KILL_MONSTERS",
        "questKillReq": {
            "CURRENT_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 2}],
            "TARGET_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 5}],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=99)
    # Flag flipped, but no list bounds error
    assert checker["complete"] is True
    # CURRENT untouched (index out of range)
    assert quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 2


def test_complete_ignores_negative_index() -> None:
    """Negative indices are also ignored (Python list semantics would wrap)."""
    quest = {
        "questReqType": "KILL_MONSTERS",
        "questKillReq": {
            "CURRENT_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 2}],
            "TARGET_KILL_MONSTER": [{"monster": "BLACKPAW", "count": 5}],
        },
    }
    checker = {"complete": False}
    mark_subtask_complete(checker, quest, sub_task_index=-1)
    assert checker["complete"] is True
    assert quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 2
