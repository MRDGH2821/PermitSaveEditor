"""Smoke test for the PySide6 GUI.

Runs the main window in the headless ``offscreen`` Qt platform. We don't
simulate user input directly — we just verify the window can be
constructed, the load path works, and the widgets are populated
correctly. Sub-task toggles are exercised by calling ``.click()`` on the
checkboxes, which Qt dispatches as a real click event.
"""

from __future__ import annotations

import os
from pathlib import Path

# Set the offscreen platform BEFORE importing PySide6 — this is the standard
# pattern for headless Qt tests on CI / Linux servers.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytestmark = pytest.mark.gui  # marker for selective runs

# Skip the whole module if PySide6 isn't installed
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from permit_save_editor.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app
    # Don't quit the app — that would break other modules


def test_window_constructs(qapp: QApplication) -> None:
    w = MainWindow()
    assert w.windowTitle() == "Potion Permit Save Editor"
    assert w._save is None  # nothing loaded
    # Save/Plain-JSON buttons should be disabled until a save is loaded
    assert not w._save_btn.isEnabled()
    assert not w._plain_btn.isEnabled()


def test_window_loads_save(qapp: QApplication, sample_json_path: Path) -> None:
    w = MainWindow()
    w.load_from_path(sample_json_path)
    assert w._save is not None
    assert w._save.character_name == "Logan"
    # Path field should now show the loaded file
    assert w._path_edit.text() == str(sample_json_path)
    # Save button is now enabled
    assert w._save_btn.isEnabled()
    assert w._plain_btn.isEnabled()
    # Unlockables tab is enabled
    assert w._tabs.isTabEnabled(1)


def test_window_populates_widgets(qapp: QApplication, sample_json_path: Path) -> None:
    w = MainWindow()
    w.load_from_path(sample_json_path)
    # Name fields
    assert w._player_name.text() == "Logan"
    assert w._dog_name.text() == "Noxe"
    # Resource spinners
    assert w._gold.value() == 500
    assert w._wood.value() == 250
    assert w._stone.value() == 100
    # Levels
    assert w._carpenter.value() == 1
    assert w._badge.value() == 1
    # Fishing
    assert w._fish1.value() == 10
    assert w._fish2.value() == 25
    assert w._fish3.value() == 75
    # Gender (sample has gender=0 -> male)
    assert w._gender_male.isChecked()
    assert not w._gender_female.isChecked()


def test_window_reads_widgets_back(qapp: QApplication, sample_json_path: Path) -> None:
    """Editing a widget and re-reading the model should pick up the change."""
    w = MainWindow()
    w.load_from_path(sample_json_path)
    w._player_name.setText("Mihir")
    w._gold.setValue(42)
    save = w._read_widgets_into_save()
    assert save.character_name == "Mihir"
    assert save.gold == 42


def test_window_bak_created_on_save(qapp: QApplication, sample_json_path: Path) -> None:
    """Saving over an existing file creates a .bak."""
    w = MainWindow()
    w.load_from_path(sample_json_path)
    # Edit and re-save (in place)
    w._player_name.setText("Edited")
    from permit_save_editor.io import save_save

    bak = sample_json_path.with_name(sample_json_path.name + ".bak")
    save_save(w._read_widgets_into_save(), sample_json_path, backup=True)
    assert bak.exists()
    # The .bak should be the original ciphered text
    assert "Logan" not in bak.read_text(encoding="utf-8")
    # The new file should contain the edited name
    from permit_save_editor.io import load_save

    reloaded = load_save(sample_json_path)
    assert reloaded.character_name == "Edited"


def test_quests_tab_is_disabled_until_load(qapp: QApplication) -> None:
    """Quests tab is hidden/disabled until a save is loaded, like Unlockables."""
    w = MainWindow()
    assert not w._tabs.isTabEnabled(2)
    assert w._tabs.tabText(2) == "Quests"


def test_quests_tab_lists_active_quests(
    qapp: QApplication, sample_json_path_with_quests: Path, sample_quests_dict
) -> None:
    """Loading a save with active quests populates the Quests tab with one entry each."""
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    assert w._tabs.isTabEnabled(2)
    assert len(w._quest_entries) == len(sample_quests_dict)
    # quest_intro is KILL_MONSTERS with 2 sub-tasks, one complete (1/2).
    first, second, third = w._quest_entries
    assert "1 / 2 complete" in first.progress_label.text()
    assert len(first.subtasks) == 2
    # quest_heal is TRIGGER_EVENT with 2 sub-tasks, none complete (0/2).
    assert "0 / 2 complete" in second.progress_label.text()
    assert len(second.subtasks) == 2
    # quest_free has no requirement checkers — no sub-task rows.
    assert "No sub-tasks" in third.progress_label.text()
    assert third.subtasks == []


def test_subtask_checkboxes_reflect_initial_state(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """Each sub-task's checkbox is pre-checked iff its checker says complete."""
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    intro = w._quest_entries[0]
    assert intro.subtasks[0].checkbox.isChecked()  # complete: True
    assert not intro.subtasks[1].checkbox.isChecked()  # complete: False


def test_subtask_checkbox_uses_requirement_text(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """The label next to each checkbox shows the requirementText, not prefixText.

    The QLabel renders the requirement as rich text (so color tags
    become Qt <font> spans), but ``.text()`` returns the plain-text
    form with the tags stripped. The underlying
    :func:`permit_save_editor.ui.main_window._render_requirement_text`
    is tested separately below.
    """
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    intro = w._quest_entries[0]
    blackpaw_label = intro.subtasks[0].label.text()
    wolf_label = intro.subtasks[1].label.text()
    # Substantive content survives (color tags are stripped by .text()).
    assert "Blackpaw" in blackpaw_label
    assert "(2/5)" in blackpaw_label
    assert "Wolf" in wolf_label
    assert "(0/3)" in wolf_label
    # Trailing tab on the raw string is stripped.
    assert not blackpaw_label.endswith("\t")
    assert not wolf_label.endswith("\t")


def test_render_requirement_text_converts_color_tags() -> None:
    """Pyglet ``<#rrggbb>...</color>`` tags become Qt ``<font color=…>`` spans."""
    from permit_save_editor.ui.main_window import _render_requirement_text

    converted = _render_requirement_text("Defeat <#ff1d1d>Blackpaw</color>\t(2/5)")
    assert "Blackpaw" in converted
    assert "(2/5)" in converted
    assert '<font color="#ff1d1d">Blackpaw</font>' in converted
    # Pyglet-style tags are gone.
    assert "<#ff1d1d>" not in converted
    assert "</color>" not in converted


def test_render_requirement_text_passes_through_unknown_text() -> None:
    """Strings without color tags are returned as-is."""
    from permit_save_editor.ui.main_window import _render_requirement_text

    assert _render_requirement_text("plain text") == "plain text"
    assert _render_requirement_text("") == ""


def test_subtask_toggle_flips_only_that_subtask(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """Checking one sub-task's checkbox must not touch any other sub-task."""
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    intro = w._quest_entries[0]
    # Pre-condition: sub-task 0 is checked, sub-task 1 is not
    assert intro.subtasks[0].checkbox.isChecked()
    assert not intro.subtasks[1].checkbox.isChecked()

    # Toggle sub-task 0 OFF
    intro.subtasks[0].checkbox.click()
    assert not intro.subtasks[0].checkbox.isChecked()
    # Sub-task 1 stays unchecked — independent state
    assert not intro.subtasks[1].checkbox.isChecked()
    # Underlying dict matches
    assert intro.quest["questRequirementCheckerList"][0]["complete"] is False
    assert intro.quest["questRequirementCheckerList"][1]["complete"] is False
    # Progress label updated
    assert "0 / 2 complete" in intro.progress_label.text()

    # Toggle sub-task 0 back ON
    intro.subtasks[0].checkbox.click()
    assert intro.subtasks[0].checkbox.isChecked()
    assert "1 / 2 complete" in intro.progress_label.text()


def test_subtask_complete_bumps_underlying_current(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """Marking a KILL_MONSTERS sub-task complete must bump CURRENT → TARGET.

    This is the whole reason the editor exists — without bumping the
    CURRENT count, the game would re-evaluate the sub-task on next load
    and reset the checker. Verifies the wiring between
    :func:`mark_subtask_complete` and the checkbox.
    """
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    intro = w._quest_entries[0]
    # Pre-condition: CURRENT_KILL_MONSTER[1] (Wolf) is 0, TARGET is 3
    kills = intro.quest["questKillReq"]
    assert kills["CURRENT_KILL_MONSTER"][0]["count"] == 2  # Blackpaw
    assert kills["CURRENT_KILL_MONSTER"][1]["count"] == 0  # Wolf
    assert kills["TARGET_KILL_MONSTER"][1]["count"] == 3

    # Mark Wolf sub-task (index 1) complete
    intro.subtasks[1].checkbox.click()

    # CURRENT bumped to TARGET for the Wolf entry only
    assert kills["CURRENT_KILL_MONSTER"][0]["count"] == 2  # Blackpaw untouched
    assert kills["CURRENT_KILL_MONSTER"][1]["count"] == 3  # Wolf bumped
    assert intro.subtasks[1].checker["complete"] is True


def test_subtask_trigger_event_complete_flips_triggered(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """TRIGGER_EVENT sub-task completion sets CURRENT[].triggered = True."""
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    heal = w._quest_entries[1]
    events = heal.quest["questEventReq"]
    assert events["CURRENT_EVENT_TRIGGERED"][0]["triggered"] is False

    # Mark the first sub-task complete
    heal.subtasks[0].checkbox.click()

    assert events["CURRENT_EVENT_TRIGGERED"][0]["triggered"] is True
    # Second sub-task's CURRENT is untouched (independence)
    assert events["CURRENT_EVENT_TRIGGERED"][1]["triggered"] is False


def test_subtask_uncheck_leaves_current_intact(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """Unchecking a sub-task must NOT reset the underlying CURRENT count.

    The user has real progress we'd rather not throw away. The flag
    flips back to False, but the in-game count is preserved.
    """
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    intro = w._quest_entries[0]
    # Blackpaw starts checked (complete=True) with CURRENT=2/5.
    # Re-check (no-op visually) then uncheck, then re-check to bump to 5.
    assert intro.subtasks[0].checkbox.isChecked()
    # Uncheck first — CURRENT must stay at 2 (the in-game value)
    intro.subtasks[0].checkbox.click()
    assert not intro.subtasks[0].checkbox.isChecked()
    assert intro.quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 2
    # Re-check — CURRENT bumps to TARGET (5)
    intro.subtasks[0].checkbox.click()
    assert intro.quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 5
    # Uncheck again — CURRENT stays at 5 (preserve real progress)
    intro.subtasks[0].checkbox.click()
    assert not intro.subtasks[0].checkbox.isChecked()
    assert intro.quest["questKillReq"]["CURRENT_KILL_MONSTER"][0]["count"] == 5


def test_subtask_state_persists_to_saved_file(
    qapp: QApplication, sample_json_path_with_quests: Path, tmp_path
) -> None:
    """Toggling a sub-task and saving writes the new state to disk."""
    from permit_save_editor.io import load_save, save_save

    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    # Mark the second sub-task of quest_intro complete
    w._quest_entries[0].subtasks[1].checkbox.click()
    # Save to a new path
    out = tmp_path / "Out.rjson"
    save_save(w._read_widgets_into_save(), out, backup=False)
    reloaded = load_save(out)
    reqs = reloaded.active_quest_list[0]["questRequirementCheckerList"]
    assert reqs[0]["complete"] is True   # unchanged from fixture
    assert reqs[1]["complete"] is True   # newly toggled


def test_quests_tab_empty_when_no_quests(qapp: QApplication, sample_json_path: Path) -> None:
    """A save with empty activeQuestList shows the placeholder, no entries."""
    w = MainWindow()
    w.load_from_path(sample_json_path)
    assert w._quest_entries == []
    # Quests tab is still enabled, just empty
    assert w._tabs.isTabEnabled(2)
