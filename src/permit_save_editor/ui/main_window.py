"""PySide6 port of the WPF ``MainWindow``.

Layout:

* Top bar: ``Browse…`` button, editable save-path field, ``Load`` button,
  ``Save`` button, ``Download Plain JSON`` button. The path field doubles as
  a status display and a manual-entry point — paste a path, hit Load.
* ``General`` tab    — name/dog name/gender, gold/wood/stone, three skill
  levels, three fishing exp slots, five color pickers.
* ``Unlockables`` tab — eight bulk-unlock buttons.
* ``Quests`` tab     — scrollable list of every active quest. Each entry
  shows the quest's name, ID, NPC, state, and requirement progress, and
  has a toggle button to mark all its requirements complete / incomplete.

The data flow is one-directional: load populates the widgets from a
``GameSaveData``; save re-reads the widgets into the same model. Mirrors the
C# ``SetInputValues`` / ``GetSaveDataAsJson`` pattern.

The Quests tab is the one exception: its toggle buttons mutate the
underlying quest dicts *in place*, so ``self._save`` stays in sync without
going through ``_read_widgets_into_save``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..io import (
    JSON_SUFFIX,
    RJSON_SUFFIX,
    dump_plain_json,
    load_save,
    save_save,
)
from ..models import Color, GameSaveData
from ..paths import default_save_dir
from .theme import apply_theme

# Validation ranges — copied from the WPF `IsValid` calls.
_GOLD_RANGE = (0, 9999)
_WOOD_RANGE = (0, 9999)
_STONE_RANGE = (0, 9999)
_LEVEL_RANGE = (0, 2)
_FISHING1_RANGE = (0, 50)
_FISHING2_RANGE = (0, 150)
_FISHING3_RANGE = (0, 300)


# Sentinel — the path field is empty by default; we don't auto-load a save.
_NO_PATH = ""


# Styles for the per-quest complete/incomplete toggle button. Two visual
# states (green = complete, grey = incomplete) so the state is obvious
# without having to read the label.
_TOGGLE_COMPLETE_QSS = (
    "QPushButton { background-color: #2e7d32; color: #fff; "
    "border: 1px solid #1b5e20; padding: 4px 12px; border-radius: 3px; }"
    "QPushButton:hover { background-color: #388e3c; }"
)
_TOGGLE_INCOMPLETE_QSS = (
    "QPushButton { background-color: #424242; color: #fff; "
    "border: 1px solid #616161; padding: 4px 12px; border-radius: 3px; }"
    "QPushButton:hover { background-color: #4f4f4f; }"
)
_TOGGLE_DISABLED_QSS = (
    "QPushButton { background-color: #303030; color: #777; "
    "border: 1px solid #3a3a3a; padding: 4px 12px; border-radius: 3px; }"
)
_ENTRY_FRAME_QSS = (
    "QFrame { background-color: #2b2b2b; border: 1px solid #3f3f46; "
    "border-radius: 4px; }"
)
_TITLE_QSS = "font-weight: bold; font-size: 13px; color: #fff;"
_SUBTITLE_QSS = "color: #999; font-size: 11px;"
_STATUS_QSS = "color: #ccc; font-size: 11px;"


@dataclass
class _QuestEntry:
    """Per-quest widgets and a reference to its source dict.

    The ``quest`` reference is the *original* dict inside
    ``self._save.active_quest_list``. Toggling the button mutates the
    dict in place, so the save model stays in sync with the UI.
    """

    frame: QFrame
    quest: dict[str, Any]
    toggle: QPushButton
    status_label: QLabel


class MainWindow(QMainWindow):
    """The save-editor window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Potion Permit Save Editor")
        self.resize(700, 480)
        self.setMinimumSize(650, 470)

        self._save: GameSaveData | None = None
        self._file_path: Path | None = None

        # Color buttons indexed by logical key ("skin", "hair", …). Populated
        # during _build_general_tab; lookups stay O(1).
        self._color_buttons: dict[str, QPushButton] = {}

        # Quests tab entries — populated by _populate_quests_from_save on
        # load; cleared on the next load or when a fresh save is built.
        self._quest_entries: list[_QuestEntry] = []
        self._quest_list_layout: QVBoxLayout | None = None

        self._build_ui()
        self._update_button_states()

    # -- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        root.addLayout(self._build_top_bar())
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_unlockables_tab(), "Unlockables")
        self._tabs.addTab(self._build_quests_tab(), "Quests")
        root.addWidget(self._tabs, 1)

    def _build_top_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFixedWidth(80)
        self._browse_btn.setToolTip("Open a file dialog to pick a .rjson / .json save.")
        self._browse_btn.clicked.connect(self._on_browse)
        bar.addWidget(self._browse_btn)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(
            "Paste a save path or use Browse… (e.g. "
            f"{default_save_dir()}/GameSave1.rjson)"
        )
        self._path_edit.returnPressed.connect(self._on_load_path)
        bar.addWidget(self._path_edit, 1)

        self._load_btn = QPushButton("Load")
        self._load_btn.setFixedWidth(60)
        self._load_btn.setToolTip("Load the save whose path is in the field above.")
        self._load_btn.clicked.connect(self._on_load_path)
        bar.addWidget(self._load_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedWidth(60)
        self._save_btn.clicked.connect(self._on_save)
        bar.addWidget(self._save_btn)

        self._plain_btn = QPushButton("Download Plain JSON")
        self._plain_btn.clicked.connect(self._on_export_plain_json)
        bar.addWidget(self._plain_btn)
        return bar

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(10, 12, 10, 12)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)

        # Names
        self._player_name = QLineEdit()
        self._player_name.setMaxLength(32)
        form.addRow("Player Name", self._player_name)

        self._dog_name = QLineEdit()
        self._dog_name.setMaxLength(32)
        form.addRow("Dog Name", self._dog_name)

        # Gender — two checkable buttons in a QButtonGroup (exclusive)
        gender_row = QWidget()
        gender_layout = QHBoxLayout(gender_row)
        gender_layout.setContentsMargins(0, 0, 0, 0)
        gender_layout.setSpacing(6)
        self._gender_male = QPushButton("Male")
        self._gender_male.setCheckable(True)
        self._gender_male.setChecked(True)
        self._gender_female = QPushButton("Female")
        self._gender_female.setCheckable(True)
        self._gender_group = QButtonGroup(self)
        self._gender_group.setExclusive(True)
        self._gender_group.addButton(self._gender_male, 0)
        self._gender_group.addButton(self._gender_female, 1)
        gender_layout.addWidget(self._gender_male)
        gender_layout.addWidget(self._gender_female)
        gender_layout.addStretch(1)
        form.addRow("Gender", gender_row)

        # Resources (gold/wood/stone) — 3-column grid
        self._gold = self._make_spin(*_GOLD_RANGE)
        self._wood = self._make_spin(*_WOOD_RANGE)
        self._stone = self._make_spin(*_STONE_RANGE)
        res_row = self._labeled_grid(
            ("Gold", self._gold),
            ("Wood", self._wood),
            ("Stone", self._stone),
        )
        form.addRow("Resources", res_row)

        # Levels (carpenter/blacksmith/badge)
        self._carpenter = self._make_spin(*_LEVEL_RANGE)
        self._blacksmith = self._make_spin(*_LEVEL_RANGE)
        self._badge = self._make_spin(*_LEVEL_RANGE)
        lvl_row = self._labeled_grid(
            ("Carpenter", self._carpenter),
            ("Blacksmith", self._blacksmith),
            ("Badge", self._badge),
        )
        form.addRow("Levels", lvl_row)

        # Fishing (3 spinboxes, with leading label inside the row)
        self._fish1 = self._make_spin(*_FISHING1_RANGE)
        self._fish2 = self._make_spin(*_FISHING2_RANGE)
        self._fish3 = self._make_spin(*_FISHING3_RANGE)
        fish_row = QWidget()
        fish_layout = QHBoxLayout(fish_row)
        fish_layout.setContentsMargins(0, 0, 0, 0)
        fish_layout.setSpacing(6)
        fish_layout.addWidget(QLabel("Fishing:"))
        fish_layout.addWidget(self._fish1)
        fish_layout.addWidget(self._fish2)
        fish_layout.addWidget(self._fish3)
        fish_layout.addStretch(1)
        form.addRow("", fish_row)

        # Colors — 5 buttons in a 5-column grid
        color_widget = QWidget()
        color_grid = QGridLayout(color_widget)
        color_grid.setContentsMargins(0, 0, 0, 0)
        color_grid.setHorizontalSpacing(8)
        color_grid.setVerticalSpacing(4)
        for col, (key, label) in enumerate(
            (
                ("skin", "Skin"),
                ("hair", "Hair"),
                ("eyes", "Eyes"),
                ("cloth", "Outfit"),
                ("cape", "Cape"),
            )
        ):
            btn = QPushButton(label)
            btn.setMinimumHeight(30)
            btn.setProperty("color_key", key)
            btn.clicked.connect(lambda _checked=False, k=key: self._pick_color(k))
            self._color_buttons[key] = btn
            color_grid.addWidget(btn, 0, col)
        form.addRow("Colors", color_widget)

        return page

    def _build_unlockables_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 12, 10, 12)
        outer.setSpacing(8)
        outer.addStretch(1)

        # Each unlock button is wired via a fixed mapping; collect them
        # once so we can iterate for state updates.
        self._unlock_buttons: dict[str, QPushButton] = {
            "skin": QPushButton("Unlock All Skins"),
            "hair": QPushButton("Unlock All Hair"),
            "cloth": QPushButton("Unlock All Cloth"),
            "cape": QPushButton("Unlock All Capes"),
            "fast_travel": QPushButton("Unlock Fast Travel"),
            "recipes": QPushButton("Unlock All Recipes"),
            "potions": QPushButton("Unlock All Potions"),
            "heal": QPushButton("Heal All"),
        }
        for key, btn in self._unlock_buttons.items():
            btn.setMinimumWidth(130)
            btn.setProperty("unlock_key", key)
            btn.clicked.connect(self._on_unlock_clicked)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        for key in ("skin", "hair", "cloth", "cape"):
            row1.addWidget(self._unlock_buttons[key])
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        for key in ("fast_travel", "recipes", "potions", "heal"):
            row2.addWidget(self._unlock_buttons[key])
        outer.addLayout(row2)

        outer.addStretch(1)
        return page

    def _build_quests_tab(self) -> QWidget:
        """Build the Quests tab: a scrollable list of per-quest entry cards.

        The scroll area is built once here. ``_populate_quests_from_save``
        is what actually fills it in, called from
        ``_populate_widgets_from_save`` on every load.
        """
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        container = QWidget()
        self._quest_list_layout = QVBoxLayout(container)
        self._quest_list_layout.setContentsMargins(6, 6, 6, 6)
        self._quest_list_layout.setSpacing(6)
        self._quest_list_layout.addStretch(1)  # push entries to the top

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)
        return page

    def _clear_quest_entries(self) -> None:
        """Tear down the per-quest widgets from the previous load.

        Safe to call even when the layout is empty.
        """
        if self._quest_list_layout is None:
            self._quest_entries.clear()
            return
        # Walk bottom-up so removing widgets doesn't reshuffle the indices
        # we're about to touch next. The trailing stretch sits at the end.
        for i in range(self._quest_list_layout.count() - 1, -1, -1):
            item = self._quest_list_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        # Re-attach the trailing stretch we just removed
        self._quest_list_layout.addStretch(1)
        self._quest_entries.clear()

    def _populate_quests_from_save(self) -> None:
        """Replace the Quests tab contents with the active quests from save.

        Empty / missing ``activeQuestList`` shows a single centred
        placeholder label. Each quest with the right shape gets an entry;
        non-dict entries (defensive — the game's JSON can drift) are
        silently skipped.
        """
        assert self._save is not None
        self._clear_quest_entries()
        quests = self._save.active_quest_list or []
        if not quests:
            placeholder = QLabel("No active quests in this save.")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #888; padding: 20px; font-size: 12px;")
            # Insert *before* the trailing stretch
            last = self._quest_list_layout.count() - 1
            self._quest_list_layout.insertWidget(last, placeholder)
            return
        for quest in quests:
            if isinstance(quest, dict):
                self._add_quest_entry(quest)

    def _add_quest_entry(self, quest: dict[str, Any]) -> None:
        """Build one quest card and append it to the scrollable list."""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(_ENTRY_FRAME_QSS)

        col = QVBoxLayout(frame)
        col.setContentsMargins(10, 8, 10, 8)
        col.setSpacing(3)

        # Title — quest name (fallback to "Unnamed quest")
        name = str(quest.get("questName") or "Unnamed quest")
        title = QLabel(name)
        title.setStyleSheet(_TITLE_QSS)
        title.setWordWrap(True)
        col.addWidget(title)

        # Subtitle — ID, NPC, state (any of which can be missing/None)
        subtitle_parts: list[str] = []
        if quest.get("questID"):
            subtitle_parts.append(f"ID: {quest['questID']}")
        giver = quest.get("questGiverName") or quest.get("npcID")
        if giver:
            subtitle_parts.append(f"NPC: {giver}")
        if quest.get("questState"):
            subtitle_parts.append(f"State: {quest['questState']}")
        if subtitle_parts:
            subtitle = QLabel("  •  ".join(subtitle_parts))
            subtitle.setStyleSheet(_SUBTITLE_QSS)
            subtitle.setWordWrap(True)
            col.addWidget(subtitle)

        # Requirement progress — count `complete: True` in the checker list
        reqs = quest.get("questRequirementCheckerList")
        if not isinstance(reqs, list) or not reqs:
            status_text = "No requirement checkers"
        else:
            done = sum(
                1
                for r in reqs
                if isinstance(r, dict) and r.get("complete") is True
            )
            status_text = f"Requirements: {done} / {len(reqs)} complete"
        status = QLabel(status_text)
        status.setStyleSheet(_STATUS_QSS)
        col.addWidget(status)

        # Toggle row — right-aligned complete/incomplete button
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        toggle_row.addStretch(1)
        toggle = QPushButton("Mark Complete")
        toggle.setCheckable(True)
        toggle.setMinimumWidth(150)
        has_reqs = isinstance(reqs, list) and len(reqs) > 0
        if not has_reqs:
            toggle.setEnabled(False)
            toggle.setToolTip("This quest has no requirement checkers to toggle.")
        is_complete = has_reqs and all(
            isinstance(r, dict) and r.get("complete") is True for r in reqs
        )
        toggle.setChecked(is_complete)
        self._style_quest_toggle(toggle, is_complete, enabled=has_reqs)
        toggle.clicked.connect(
            lambda _checked=False, t=toggle, e=len(self._quest_entries): (
                self._on_quest_toggle(t, e)
            )
        )
        toggle_row.addWidget(toggle)
        col.addLayout(toggle_row)

        # Append before the trailing stretch
        last = self._quest_list_layout.count() - 1
        self._quest_list_layout.insertWidget(last, frame)
        self._quest_entries.append(
            _QuestEntry(frame=frame, quest=quest, toggle=toggle, status_label=status)
        )

    @staticmethod
    def _style_quest_toggle(btn: QPushButton, checked: bool, *, enabled: bool) -> None:
        """Apply green/grey styling to a quest toggle button."""
        if not enabled:
            btn.setText("No requirements")
            btn.setStyleSheet(_TOGGLE_DISABLED_QSS)
            return
        if checked:
            btn.setText("Complete ✓")
            btn.setStyleSheet(_TOGGLE_COMPLETE_QSS)
        else:
            btn.setText("Mark Complete")
            btn.setStyleSheet(_TOGGLE_INCOMPLETE_QSS)

    def _on_quest_toggle(self, btn: QPushButton, entry_index: int) -> None:
        """Mark all of a quest's requirement checkers complete / incomplete.

        Mutates ``self._save.active_quest_list[i]`` in place so the save
        model stays in sync with the UI without going through
        ``_read_widgets_into_save``. Also refreshes the per-entry status
        label so the "X / Y complete" counter updates immediately.
        """
        if entry_index < 0 or entry_index >= len(self._quest_entries):
            return
        entry = self._quest_entries[entry_index]
        if btn is not entry.toggle:
            # Stale signal (defensive — shouldn't happen with current wiring)
            return
        checked = btn.isChecked()
        reqs = entry.quest.get("questRequirementCheckerList")
        if not isinstance(reqs, list):
            return
        for r in reqs:
            if isinstance(r, dict):
                r["complete"] = bool(checked)
        # Refresh the per-entry counter
        done = sum(
            1 for r in reqs if isinstance(r, dict) and r.get("complete") is True
        )
        entry.status_label.setText(f"Requirements: {done} / {len(reqs)} complete")
        self._style_quest_toggle(btn, checked, enabled=True)

    # -- small UI helpers ------------------------------------------------

    @staticmethod
    def _make_spin(min_: int, max_: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_, max_)
        return s

    @staticmethod
    def _labeled_grid(*pairs: tuple[str, QSpinBox]) -> QWidget:
        """3-column grid: ``[label] [spin] [label] [spin] [label] [spin]``."""
        w = QWidget()
        layout = QGridLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        for i, (label, spin) in enumerate(pairs):
            layout.addWidget(QLabel(label), 0, i * 2)
            layout.addWidget(spin, 0, i * 2 + 1)
            layout.setColumnStretch(i * 2 + 1, 1)
        return w

    # -- Load / save flow -------------------------------------------------

    def load_from_path(self, path: Path) -> None:
        """Load a save from disk and populate the widgets."""
        try:
            self._save = load_save(path)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Error", f"Failed to load save file:\n{exc}")
            return
        self._file_path = path
        self._path_edit.setText(str(path))
        self._populate_widgets_from_save()
        self._update_button_states()

    def _populate_widgets_from_save(self) -> None:
        assert self._save is not None
        s = self._save
        self._player_name.setText(s.character_name)
        self._dog_name.setText(s.dog_name)
        if s.gender == 1:
            self._gender_female.setChecked(True)
        else:
            self._gender_male.setChecked(True)
        self._gold.setValue(s.gold)
        self._wood.setValue(s.wood)
        self._stone.setValue(s.stone)
        self._carpenter.setValue(s.carpenter_level)
        self._blacksmith.setValue(s.blacksmith_level)
        self._badge.setValue(s.badge_level)
        fishing = s.fish_exp_dict.values
        self._fish1.setValue(fishing[0] if len(fishing) > 0 else 0)
        self._fish2.setValue(fishing[1] if len(fishing) > 1 else 0)
        self._fish3.setValue(fishing[2] if len(fishing) > 2 else 0)
        for key, attr in (
            ("skin", "skin_color"),
            ("hair", "hair_color"),
            ("eyes", "eyes_color"),
            ("cloth", "cloth_color"),
            ("cape", "cape_color"),
        ):
            self._apply_color_button(key, getattr(s, attr))
        # Quests tab — rebuild entries from the active quest list
        self._populate_quests_from_save()

    def _read_widgets_into_save(self) -> GameSaveData:
        """Rebuild the GameSaveData from the current widget state.

        If nothing has been loaded yet, start from a fresh model (mirrors
        the C# ``_loadedSave ??= new GameSaveData()`` pattern).
        """
        if self._save is None:
            self._save = GameSaveData()
        s = self._save
        s.character_name = self._player_name.text() or "Logan"
        s.dog_name = self._dog_name.text() or "Noxe"
        gender_id = self._gender_group.checkedId()
        s.gender = gender_id if gender_id >= 0 else 0
        s.gold = self._gold.value()
        s.wood = self._wood.value()
        s.stone = self._stone.value()
        s.carpenter_level = self._carpenter.value()
        s.blacksmith_level = self._blacksmith.value()
        s.badge_level = self._badge.value()
        # FishExpDict.values is a list — keep it at length 3
        new_fish = [
            self._fish1.value(),
            self._fish2.value(),
            self._fish3.value(),
        ]
        s.fish_exp_dict.values = new_fish
        for key, attr in (
            ("skin", "skin_color"),
            ("hair", "hair_color"),
            ("eyes", "eyes_color"),
            ("cloth", "cloth_color"),
            ("cape", "cape_color"),
        ):
            setattr(s, attr, self._read_color_button(key))
        return s

    def _update_button_states(self) -> None:
        """Enable/disable buttons that need a loaded save."""
        loaded = self._save is not None
        self._save_btn.setEnabled(loaded)
        self._plain_btn.setEnabled(loaded)
        for btn in self._unlock_buttons.values():
            btn.setEnabled(loaded)
        # Unlockables + Quests tabs are only meaningful with a loaded save
        # (mirrors the original WPF — they're hidden until a save loads).
        self._tabs.setTabEnabled(1, loaded)
        self._tabs.setTabEnabled(2, loaded)

    # -- Slots ------------------------------------------------------------

    def _on_browse(self) -> None:
        start_dir = str(default_save_dir())
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Load Data",
            start_dir,
            f"Potion Permit Save data (*{RJSON_SUFFIX} *{JSON_SUFFIX});;All files (*)",
        )
        if not path_str:
            return
        self.load_from_path(Path(path_str))

    def _on_load_path(self) -> None:
        """Load whatever path is in the path field (manual entry)."""
        text = self._path_edit.text().strip()
        if not text or text == _NO_PATH:
            QMessageBox.information(
                self,
                "No path",
                "Enter a save file path in the field above, or use Browse….",
            )
            return
        path = Path(text).expanduser()
        if not path.exists():
            QMessageBox.critical(self, "Error", f"File not found:\n{path}")
            return
        self.load_from_path(path)

    def _on_save(self) -> None:
        if self._save is None:
            return
        save = self._read_widgets_into_save()

        # Default save name: reuse the loaded file's name, or GameSave1.
        if self._file_path is not None:
            default_name = self._file_path.name
        else:
            default_name = "GameSave1" + RJSON_SUFFIX
        start_dir = str(
            self._file_path.parent if self._file_path else default_save_dir()
        )
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Data",
            str(Path(start_dir) / default_name),
            f"Potion Permit Save data (*{RJSON_SUFFIX})",
        )
        if not path_str:
            return
        out_path = Path(path_str)
        try:
            save_save(save, out_path, backup=out_path.exists())
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
            return

        self._file_path = out_path
        self._path_edit.setText(str(out_path))
        QMessageBox.information(self, "Save", "Save Successful!")

    def _on_export_plain_json(self) -> None:
        if self._save is None:
            return
        save = self._read_widgets_into_save()
        start_dir = str(
            self._file_path.parent if self._file_path else default_save_dir()
        )
        default_name = (
            self._file_path.with_suffix(JSON_SUFFIX).name
            if self._file_path
            else "GameSave" + JSON_SUFFIX
        )
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Data (plain JSON)",
            str(Path(start_dir) / default_name),
            f"Plain JSON (*{JSON_SUFFIX})",
        )
        if not path_str:
            return
        try:
            dump_plain_json(save, Path(path_str))
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{exc}")

    def _on_unlock_clicked(self) -> None:
        if self._save is None:
            return
        save = self._read_widgets_into_save()
        sender = self.sender()
        if sender is None:
            return
        key = sender.property("unlock_key")
        if key in ("skin", "hair", "cloth", "cape"):
            attr = f"{key}_lock_state_list"
            target = getattr(save, attr)
            for i in range(len(target)):
                target[i] = True
        elif key == "fast_travel":
            save.fast_travel_state.unlock_all()
        elif key == "recipes":
            save.recipe_lock_state.unlock_all()
        elif key == "potions":
            save.potion_lock_state.unlock_all()
        elif key == "heal":
            save.heal_all_npcs()
        self._save = save

    # -- Color pickers ----------------------------------------------------

    def _apply_color_button(self, key: str, color: Color) -> None:
        """Set the color button's appearance to ``color`` and cache the RGBA."""
        r, g, b, a = color.to_qcolor()
        hex_ = f"#{r:02x}{g:02x}{b:02x}"
        # Pick black/white text for legibility depending on background luma
        luma = r * 299 + g * 587 + b * 114
        text_color = "#000" if luma > 128000 else "#fff"
        btn = self._color_buttons[key]
        btn.setText(hex_.upper())
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_}; color: {text_color}; "
            f"border: 1px solid #3f3f46; }}"
        )
        btn.setProperty("color_rgba", (r, g, b, a))

    def _read_color_button(self, key: str) -> Color:
        rgba = self._color_buttons[key].property("color_rgba")
        if rgba is None:
            return Color()
        r, g, b, a = rgba
        return Color.from_qcolor(r, g, b, a)

    def _pick_color(self, key: str) -> None:
        btn = self._color_buttons[key]
        rgba = btn.property("color_rgba") or (200, 200, 200, 255)
        chosen = QColorDialog.getColor(QColor(*rgba[:3]), self, "Pick color")
        if not chosen.isValid():
            return
        self._apply_color_button(
            key,
            Color.from_qcolor(chosen.red(), chosen.green(), chosen.blue(), chosen.alpha()),
        )


# -- Entry point ---------------------------------------------------------


def run_gui(initial_path: Path | None = None) -> None:
    """Launch the GUI. Blocks until the user closes the window.

    Set the ``QT_QPA_PLATFORM=offscreen`` environment variable to run
    headless (used by the smoke test).
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow()
    window.show()
    if initial_path is not None:
        window.load_from_path(initial_path)
    app.exec()


__all__ = ["MainWindow", "run_gui"]
