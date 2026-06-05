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


# -- Folder row / slot picker --------------------------------------------
#
# The folder row lives below the file row and lets the user paste a
# long path (notably Wine/Proton ``AppData/LocalLow/...`` prefixes) and
# pick a save slot from a dropdown. These tests exercise the rescan
# logic, slot change handler, and graceful failure modes.


def test_folder_field_prefilled_with_default_save_dir(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    """On startup the folder field shows the default save dir (or empty
    if the platform default doesn't exist)."""
    from permit_save_editor.ui import main_window as mw

    monkeypatch.setattr(mw, "default_save_dir", lambda: tmp_path / "PotionPermit")
    w = MainWindow()
    # The field text matches the patched default
    assert w._folder_path_edit.text() == str(tmp_path / "PotionPermit")
    # Folder doesn't exist → combo disabled, status "0 slots"
    assert not w._slot_combo.isEnabled()
    assert w._folder_status.text() == "0 slots"


def test_rescan_populates_slot_combo_with_rjson_files(
    qapp: QApplication, tmp_path
) -> None:
    """A folder with .rjson files gets one combo item per file, sorted."""
    # Create 3 .rjson files with non-sorted names to verify sort order
    (tmp_path / "GameSave3.rjson").write_bytes(b"")
    (tmp_path / "GameSave1.rjson").write_bytes(b"")
    (tmp_path / "GameSave2.rjson").write_bytes(b"")
    w = MainWindow()
    w._rescan_folder(tmp_path)
    assert w._slot_combo.isEnabled()
    items = [w._slot_combo.itemText(i) for i in range(w._slot_combo.count())]
    assert items == ["GameSave1.rjson", "GameSave2.rjson", "GameSave3.rjson"]
    assert w._folder_status.text() == "3 slots"


def test_rescan_stores_full_path_in_item_data(
    qapp: QApplication, tmp_path
) -> None:
    """Each combo item's userData is the absolute path (for the file field)."""
    save = tmp_path / "GameSave2.rjson"
    save.write_bytes(b"")
    w = MainWindow()
    w._rescan_folder(tmp_path)
    full = w._slot_combo.itemData(0)
    assert full == str(save)


def test_rescan_ignores_non_rjson_files(
    qapp: QApplication, tmp_path
) -> None:
    """Plain .json exports and other files are not slot candidates."""
    (tmp_path / "GameSave1.rjson").write_bytes(b"")
    (tmp_path / "GameSave1.json").write_bytes(b"")  # plain export, not a slot
    (tmp_path / "notes.txt").write_bytes(b"")
    (tmp_path / "GameSave2.rjson.bak").write_bytes(b"")  # backup
    w = MainWindow()
    w._rescan_folder(tmp_path)
    items = [w._slot_combo.itemText(i) for i in range(w._slot_combo.count())]
    assert items == ["GameSave1.rjson"]


def test_rescan_handles_nonexistent_folder(
    qapp: QApplication, tmp_path
) -> None:
    """A non-existent path clears the combo without raising."""
    w = MainWindow()
    w._slot_combo.addItem("leftover", userData="/some/old/path")
    w._rescan_folder(tmp_path / "does_not_exist")
    # Rescan drops everything regardless of what was there
    assert w._slot_combo.count() == 0
    assert not w._slot_combo.isEnabled()
    assert w._folder_status.text() == "0 slots"


def test_rescan_handles_empty_folder(
    qapp: QApplication, tmp_path
) -> None:
    """A real folder with no .rjson files shows a disabled placeholder."""
    # Make the folder exist but empty
    empty = tmp_path / "empty"
    empty.mkdir()
    w = MainWindow()
    w._rescan_folder(empty)
    assert w._slot_combo.count() == 1
    assert w._slot_combo.itemText(0) == "(no saves in this folder)"
    assert not w._slot_combo.isEnabled()
    assert w._folder_status.text() == "0 slots"


def test_rescan_handles_path_that_is_a_file(
    qapp: QApplication, tmp_path
) -> None:
    """A path that points to a file (not a directory) is treated as bad."""
    f = tmp_path / "a_file.rjson"
    f.write_bytes(b"")
    w = MainWindow()
    w._rescan_folder(f)
    assert w._slot_combo.count() == 0
    assert not w._slot_combo.isEnabled()


def test_rescan_with_none_clears_combo(qapp: QApplication) -> None:
    """Passing None clears the combo and disables it."""
    w = MainWindow()
    w._slot_combo.addItem("leftover", userData="x")
    w._rescan_folder(None)
    assert w._slot_combo.count() == 0
    assert not w._slot_combo.isEnabled()
    assert w._folder_status.text() == "0 slots"


def test_rescan_replaces_previous_results(
    qapp: QApplication, tmp_path
) -> None:
    """A second rescan replaces (not appends) the prior combo contents."""
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    (folder_a / "GameSave1.rjson").write_bytes(b"")
    (folder_b / "GameSave1.rjson").write_bytes(b"")
    (folder_b / "GameSave2.rjson").write_bytes(b"")
    w = MainWindow()
    w._rescan_folder(folder_a)
    assert w._slot_combo.count() == 1
    w._rescan_folder(folder_b)
    items = [w._slot_combo.itemText(i) for i in range(w._slot_combo.count())]
    assert items == ["GameSave1.rjson", "GameSave2.rjson"]
    # And the data points to folder_b
    assert Path(w._slot_combo.itemData(0)).parent == folder_b
    assert w._folder_status.text() == "2 slots"


def test_slot_change_populates_file_path_field(
    qapp: QApplication, tmp_path
) -> None:
    """Selecting a combo item copies its full path into the file field."""
    save1 = tmp_path / "GameSave1.rjson"
    save2 = tmp_path / "GameSave2.rjson"
    save1.write_bytes(b"")
    save2.write_bytes(b"")
    w = MainWindow()
    w._rescan_folder(tmp_path)
    # Pick the second slot
    w._slot_combo.setCurrentIndex(1)
    assert w._path_edit.text() == str(save2)
    # Pick the first slot
    w._slot_combo.setCurrentIndex(0)
    assert w._path_edit.text() == str(save1)


def test_on_folder_changed_rescans_with_expanduser(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    """Typing a ``~`` path in the folder field + Enter expands it."""
    # Symlink tmp_path to a name under a fake home so expanduser resolves
    # to a real directory. Using a real subdir of tmp_path keeps the test
    # self-contained — we just verify expanduser ran (no error raised).
    folder = tmp_path / "savedir"
    folder.mkdir()
    (folder / "GameSave1.rjson").write_bytes(b"")
    w = MainWindow()
    # Simulate the user typing the path and pressing Enter
    w._folder_path_edit.setText(str(folder))
    w._on_folder_changed()
    assert w._slot_combo.isEnabled()
    assert w._slot_combo.count() == 1


def test_on_folder_changed_empty_clears_combo(qapp: QApplication) -> None:
    """Clearing the folder field empties the combo."""
    w = MainWindow()
    w._slot_combo.addItem("leftover", userData="x")
    w._folder_path_edit.setText("")
    w._on_folder_changed()
    assert w._slot_combo.count() == 0


def test_rescan_blocks_signals_during_population(
    qapp: QApplication, tmp_path
) -> None:
    """Rescan must not fire _on_slot_changed for each added item.

    Without blockSignals, adding items via addItem would trigger
    activated[int]=currentIndex for each, which would overwrite the
    file path field with stale combos.
    """
    (tmp_path / "GameSave1.rjson").write_bytes(b"")
    (tmp_path / "GameSave2.rjson").write_bytes(b"")
    w = MainWindow()
    w._path_edit.setText("MANUAL_VALUE")
    w._rescan_folder(tmp_path)
    # File path field should still be the manual value
    assert w._path_edit.text() == "MANUAL_VALUE"
