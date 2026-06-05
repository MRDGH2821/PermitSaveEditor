"""Per-sub-task completion logic for quest entries.

A quest in this game is rarely a single "kill one monster" — it's a list
of sub-tasks (``questRequirementCheckerList``), one per sub-objective.
Each sub-task has its own ``complete: bool`` flag *and* an underlying
``CURRENT_X`` value in the quest's ``*Req`` dict (the actual progress
count, e.g. ``CURRENT_KILL_MONSTER[0].count = 2``).

Just flipping the checker is fragile: the game's logic reads the
``CURRENT`` values and may re-evaluate the quest on next save, resetting
the checker if the underlying counts don't match ``TARGET``. So this
module also bumps the relevant ``CURRENT`` to ``TARGET`` when marking
complete, mirroring what the game itself does when a sub-task is done.

Incomplete (``uncheck``) is intentionally minimal: it only flips the
checker flag. We do **not** zero out the player's progress counts, since
that would silently destroy real progress the player might want to keep.
"""

from __future__ import annotations

from typing import Any


def mark_subtask_complete(
    checker: dict[str, Any],
    quest: dict[str, Any],
    sub_task_index: int,
) -> None:
    """Mark sub-task at ``sub_task_index`` complete and bump its CURRENT_X.

    The sub-task's position in ``questRequirementCheckerList`` corresponds
    positionally to its entry in the quest's ``CURRENT_X`` / ``TARGET_X``
    arrays (e.g. checker 2 → ``CURRENT_KILL_MONSTER[2]``). Only that
    index is bumped — the others are left as the player has them.

    No-op on a non-dict checker or an out-of-range index.
    """
    if not isinstance(checker, dict):
        return
    checker["complete"] = True

    req_type = quest.get("questReqType", "")
    if req_type == "KILL_MONSTERS":
        _bump_index_count(
            quest.get("questKillReq"),
            "CURRENT_KILL_MONSTER",
            "TARGET_KILL_MONSTER",
            sub_task_index,
        )
    elif req_type == "TALK_WITH_NPC":
        _bump_index_count(
            quest.get("questTalkReq"),
            "CURRENT_TALK_WITH_NPC",
            "TARGET_TALK_WITH_NPC",
            sub_task_index,
        )
    elif req_type == "TRIGGER_EVENT":
        _bump_index_flag(
            quest.get("questEventReq"),
            sub_task_index,
            "triggered",
            True,
        )
    elif req_type == "ITEM_DELIVERY":
        _bump_index_count(
            quest.get("questDeliveryReq"),
            "CURRENT_DELIVERY",
            "TARGET_DELIVERY",
            sub_task_index,
        )
    # COLLECT_ITEMS has no CURRENT — count is inferred from the player's
    # inventory, which the editor doesn't (and shouldn't) touch.
    # PROGRESS uses scalar fields (not parallel arrays) so the index is
    # irrelevant — bump every CURRENT_X scalar to its TARGET_X counterpart:
    elif req_type == "PROGRESS":
        _copy_progress_scalars(quest.get("questProgressReq"))


def mark_subtask_incomplete(checker: dict[str, Any]) -> None:
    """Flip a sub-task's checker back to incomplete. Leaves CURRENT_X intact.

    We deliberately do **not** reset the underlying progress counts — the
    player has done real work and we'd rather not throw it away. If they
    want a fresh start, they can mark complete again (which bumps back to
    TARGET) and then re-load the save in-game.
    """
    if isinstance(checker, dict):
        checker["complete"] = False


# ---- internal helpers ---------------------------------------------------


def _bump_index_count(
    req_dict: Any,
    current_key: str,
    target_key: str,
    index: int,
) -> None:
    """Set the ``count`` field of CURRENT[index] to TARGET[index]'s count."""
    if not isinstance(req_dict, dict):
        return
    current = req_dict.get(current_key)
    target = req_dict.get(target_key)
    if not isinstance(current, list) or not isinstance(target, list):
        return
    if index < 0 or index >= len(current):
        return
    cur_entry = current[index]
    if not isinstance(cur_entry, dict):
        return
    if index >= len(target):
        return
    tgt_entry = target[index]
    if isinstance(tgt_entry, dict) and "count" in tgt_entry:
        cur_entry["count"] = tgt_entry["count"]


def _bump_index_flag(
    req_dict: Any,
    index: int,
    flag: str,
    value: bool,
) -> None:
    """Set a boolean flag (e.g. ``triggered``) on CURRENT_EVENT_TRIGGERED[index]."""
    if not isinstance(req_dict, dict):
        return
    current = req_dict.get("CURRENT_EVENT_TRIGGERED")
    if not isinstance(current, list) or index < 0 or index >= len(current):
        return
    entry = current[index]
    if isinstance(entry, dict):
        entry[flag] = value


def _copy_progress_scalars(req_dict: Any) -> None:
    """Set every ``CURRENT_X`` scalar to its ``TARGET_X`` counterpart.

    Covers the FP/town-upgrade/cauldron quest type, which uses flat
    scalar fields like ``CURRENT_FP_COUNT`` / ``TARGET_FP_COUNT``.
    Non-numeric fields (e.g. ``CURRENT_EVENT_TAG``) are skipped.
    """
    if not isinstance(req_dict, dict):
        return
    for key in list(req_dict.keys()):
        if not key.startswith("CURRENT_"):
            continue
        if not isinstance(req_dict[key], (int, float)):
            continue
        target_key = "TARGET_" + key[len("CURRENT_") :]
        if target_key in req_dict and isinstance(req_dict[target_key], (int, float)):
            req_dict[key] = req_dict[target_key]
