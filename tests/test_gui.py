"""Smoke test for the PySide6 GUI.

Runs the main window in the headless ``offscreen`` Qt platform. We don't
simulate user input — we just verify the window can be constructed, the
load path works, and the widgets are populated correctly.
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
    # The first quest is partially complete (1/3), the second is incomplete (0/2),
    # the third has no requirements and the toggle should be disabled.
    first, second, third = w._quest_entries
    assert "1 / 3 complete" in first.status_label.text()
    assert "0 / 2 complete" in second.status_label.text()
    assert "No requirement checkers" in third.status_label.text()
    assert not first.toggle.isChecked()
    assert not second.toggle.isChecked()
    assert not third.toggle.isEnabled()  # no requirements → disabled toggle


def test_quest_toggle_mutates_underlying_dict(
    qapp: QApplication, sample_json_path_with_quests: Path
) -> None:
    """Toggling a quest's button flips every requirement's ``complete`` flag in the save."""
    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    second = w._quest_entries[1]
    # Pre-condition: 0/2 complete
    assert all(
        r["complete"] is False for r in second.quest["questRequirementCheckerList"]
    )

    # Simulate the user clicking "Mark Complete"
    second.toggle.click()
    assert second.toggle.isChecked()
    # Underlying dict is mutated in place — every requirement is now True
    assert all(
        r["complete"] is True for r in second.quest["questRequirementCheckerList"]
    )
    # The status label updates immediately
    assert "2 / 2 complete" in second.status_label.text()
    # The save model is the same object — its active_quest_list reflects the change
    save_reqs = w._save.active_quest_list[1]["questRequirementCheckerList"]
    assert all(r["complete"] is True for r in save_reqs)

    # Clicking again flips them back to incomplete
    second.toggle.click()
    assert not second.toggle.isChecked()
    assert all(
        r["complete"] is False for r in second.quest["questRequirementCheckerList"]
    )
    assert "0 / 2 complete" in second.status_label.text()


def test_quest_toggle_persists_to_saved_file(
    qapp: QApplication, sample_json_path_with_quests: Path, tmp_path
) -> None:
    """Toggling and then saving writes the new state to disk and round-trips it."""
    from permit_save_editor.io import load_save, save_save

    w = MainWindow()
    w.load_from_path(sample_json_path_with_quests)
    # Mark the first quest complete
    w._quest_entries[0].toggle.click()
    # Save to a new path
    out = tmp_path / "Out.rjson"
    save_save(w._read_widgets_into_save(), out, backup=False)
    reloaded = load_save(out)
    reqs = reloaded.active_quest_list[0]["questRequirementCheckerList"]
    assert all(r["complete"] is True for r in reqs)


def test_quests_tab_empty_when_no_quests(qapp: QApplication, sample_json_path: Path) -> None:
    """A save with empty activeQuestList shows the placeholder, no entries."""
    w = MainWindow()
    w.load_from_path(sample_json_path)
    assert w._quest_entries == []
    # Quests tab is still enabled, just empty
    assert w._tabs.isTabEnabled(2)
