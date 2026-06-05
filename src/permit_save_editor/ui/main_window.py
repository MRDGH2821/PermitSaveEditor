"""PySide6 port of the WPF ``MainWindow``.

Layout:

* Top bar is two rows:
  - **File row** — ``Browse File…`` button, editable save-path field,
    ``Load`` / ``Save`` / ``Download Plain JSON`` buttons. Paste a path,
    hit ``Load``.
  - **Folder row** — ``Browse Folder…`` button, editable folder-path
    field, ``Slot: GameSaveN.rjson  ▼`` dropdown, slot count label.
    The folder row is friendlier for Wine/Proton users (Heroic, Lutris,
    Steam) who want to paste a long ``AppData/LocalLow`` prefix path
    and pick a save slot from a dropdown rather than wrestle with a
    file dialog. Either row works to load a save.
* ``General`` tab    — name/dog name/gender, gold/wood/stone, three skill
  levels, three fishing exp slots, five color pickers.
* ``Unlockables`` tab — eight bulk-unlock buttons.
* ``Quests`` tab     — scrollable list of every active quest. Each entry
  shows the quest's name, ID, NPC, state, and overall sub-task progress,
  and renders one toggleable row per sub-task. Toggling a row flips the
  checker's ``complete`` flag *and* bumps the underlying ``CURRENT_X``
  progress value to ``TARGET_X``, so the game treats the sub-task as
  actually done (see :mod:`permit_save_editor.quest_progress`).

The data flow is one-directional: load populates the widgets from a
``GameSaveData``; save re-reads the widgets into the same model. Mirrors the
C# ``SetInputValues`` / ``GetSaveDataAsJson`` pattern.

The Quests tab is the one exception: its toggle buttons mutate the
underlying quest dicts *in place* (via ``mark_subtask_complete`` /
``mark_subtask_incomplete``), so ``self._save`` stays in sync without
going through ``_read_widgets_into_save``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
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
from ..quest_progress import mark_subtask_complete, mark_subtask_incomplete
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


# Styles for per-quest card and labels. Two label sizes (title bold,
# subtitle/requirement grey) plus the card frame.
_ENTRY_FRAME_QSS = (
    "QFrame { background-color: #2b2b2b; border: 1px solid #3f3f46; "
    "border-radius: 4px; }"
)
_TITLE_QSS = "font-weight: bold; font-size: 13px; color: #fff;"
_SUBTITLE_QSS = "color: #999; font-size: 11px;"
_STATUS_QSS = "color: #ccc; font-size: 11px;"


# Pyglet-style inline color tags inside ``requirementText`` look like
# ``<#ff1d1d>Blackpaw</color>``. Qt rich text doesn't understand that
# syntax, so we convert each pair to a real ``<font color="#…">…</font>``
# element before handing the string to a QLabel. Anything that doesn't
# match is left as-is (so weird future variants just render verbatim).
_COLOR_TAG_RE = re.compile(r"<#([0-9a-fA-F]{6})>(.*?)</color>", re.DOTALL)


def _render_requirement_text(text: str) -> str:
    """Convert Pyglet color tags in a requirementText into Qt rich text.

    Examples
    --------
    >>> _render_requirement_text("Defeat <#ff1d1d>Blackpaw</color>\\t(2/5)")
    'Defeat <font color="#ff1d1d">Blackpaw</font>\\t(2/5)'
    """
    return _COLOR_TAG_RE.sub(r'<font color="#\1">\2</font>', text)


@dataclass
class _SubTaskRow:
    """A single sub-task's checkbox + the checker dict it controls.

    The ``checker`` reference is the *original* dict inside
    ``questRequirementCheckerList``. Toggling the checkbox mutates the
    dict in place (via :func:`mark_subtask_complete` /
    :func:`mark_subtask_incomplete`), so the save model stays in sync.
    ``label`` is kept so tests / future code can find the row's text
    widget without walking the whole frame's children.
    """

    checkbox: QCheckBox
    label: QLabel
    checker: dict[str, Any]


@dataclass
class _QuestEntry:
    """Per-quest widgets and a reference to its source dict.

    The ``quest`` reference is the *original* dict inside
    ``self._save.active_quest_list``. The ``subtasks`` list holds one
    :class:`_SubTaskRow` per entry in ``questRequirementCheckerList``,
    preserving the positional index for the CURRENT_X bump in
    :mod:`permit_save_editor.quest_progress`.
    """

    frame: QFrame
    quest: dict[str, Any]
    subtasks: list[_SubTaskRow]
    progress_label: QLabel  # "Sub-tasks: 1 / 3 complete"


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
        # Pre-fill the folder row with the platform-native save dir
        # and scan it so the user sees available slots immediately.
        # Wine/Proton users can then paste over this and rescan.
        self._folder_path_edit.setText(str(default_save_dir()))
        self._rescan_folder(default_save_dir())
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

    def _build_top_bar(self) -> QVBoxLayout:
        """Two-row top bar: file mode (existing) + folder mode (new).

        Row 1 — file mode:
            ``[Browse File…] [file path field] [Load] [Save] [Download Plain JSON]``

        Row 2 — folder mode:
            ``[Browse Folder…] [folder path field] [Slot: GameSave1.rjson  ▼]  N slots``

        Either row works to load a save; row 2 is friendlier for
        Wine/Proton users who want to paste a long ``AppData/LocalLow``
        prefix path and pick a save slot from a dropdown rather than
        wrestle with a file dialog.
        """
        bar = QVBoxLayout()
        bar.setSpacing(4)
        bar.addLayout(self._build_file_row())
        bar.addLayout(self._build_folder_row())
        return bar

    def _build_file_row(self) -> QHBoxLayout:
        """File mode: pick a single .rjson/.json file and load it.

        Identical to the pre-folder-row behaviour — Browse opens a
        file dialog, the path field accepts pasted paths, Load is the
        universal trigger.
        """
        row = QHBoxLayout()
        row.setSpacing(8)

        self._browse_btn = QPushButton("Browse File…")
        self._browse_btn.setFixedWidth(100)
        self._browse_btn.setToolTip(
            "Open a file dialog to pick a .rjson / .json save file."
        )
        self._browse_btn.clicked.connect(self._on_browse)
        row.addWidget(self._browse_btn)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(
            "Paste a save path or use Browse… (e.g. "
            f"{default_save_dir()}/GameSave1.rjson)"
        )
        self._path_edit.returnPressed.connect(self._on_load_path)
        row.addWidget(self._path_edit, 1)

        self._load_btn = QPushButton("Load")
        self._load_btn.setFixedWidth(60)
        self._load_btn.setToolTip("Load the save whose path is in the field above.")
        self._load_btn.clicked.connect(self._on_load_path)
        row.addWidget(self._load_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedWidth(60)
        self._save_btn.clicked.connect(self._on_save)
        row.addWidget(self._save_btn)

        self._plain_btn = QPushButton("Download Plain JSON")
        self._plain_btn.clicked.connect(self._on_export_plain_json)
        row.addWidget(self._plain_btn)
        return row

    def _build_folder_row(self) -> QHBoxLayout:
        """Folder mode: pick a save folder, then choose a slot from the dropdown.

        The folder field is editable (paste-friendly) and pre-populated
        with :func:`default_save_dir` on startup. ``Browse Folder…``
        opens a directory picker, the slot combo below is populated
        with ``*.rjson`` files in the chosen folder, and selecting a
        slot copies its full path into the file-row field so a
        subsequent ``Load`` opens it.
        """
        row = QHBoxLayout()
        row.setSpacing(8)

        self._browse_folder_btn = QPushButton("Browse Folder…")
        self._browse_folder_btn.setFixedWidth(100)
        self._browse_folder_btn.setToolTip(
            "Open a directory picker to choose the folder containing "
            "the .rjson save slots."
        )
        self._browse_folder_btn.clicked.connect(self._on_browse_folder)
        row.addWidget(self._browse_folder_btn)

        self._folder_path_edit = QLineEdit()
        self._folder_path_edit.setPlaceholderText(
            "Save folder — paste a path (Wine/Proton users see tooltip)"
        )
        self._folder_path_edit.setToolTip(
            "Path to the folder containing GameSave1.rjson, "
            "GameSave2.rjson, etc.\n\n"
            "Defaults to the native Linux save location, but Wine/Proton "
            "(Heroic, Lutris, Steam) users should paste their prefix path:\n"
            "  <prefix>/drive_c/users/steamuser/AppData/LocalLow/"
            "MasshiveMedia/Potion Permit"
        )
        # Rescan on Enter or focus-out so the user can paste + see slots.
        self._folder_path_edit.returnPressed.connect(self._on_folder_changed)
        row.addWidget(self._folder_path_edit, 1)

        slot_label = QLabel("Slot:")
        slot_label.setStyleSheet(_STATUS_QSS)
        row.addWidget(slot_label)

        self._slot_combo = QComboBox()
        self._slot_combo.setMinimumWidth(170)
        self._slot_combo.setToolTip(
            "All .rjson files in the folder above, sorted. "
            "Selecting a slot copies its full path into the file field."
        )
        # currentIndexChanged (not ``activated``) so programmatic
        # changes (e.g. tests using setCurrentIndex, or future
        # auto-pick behaviour) also propagate. ``_rescan_folder``
        # wraps the population in blockSignals() so the clear+repopulate
        # cycle doesn't fire a spurious slot-change event.
        self._slot_combo.currentIndexChanged.connect(self._on_slot_changed)
        self._slot_combo.setEnabled(False)  # populated on first scan
        row.addWidget(self._slot_combo)

        self._folder_status = QLabel("0 slots")
        self._folder_status.setStyleSheet(_STATUS_QSS)
        self._folder_status.setFixedWidth(60)
        row.addWidget(self._folder_status)
        return row

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
        """Build one quest card and append it to the scrollable list.

        The card shows the quest's metadata (name, ID, NPC, state) and
        one toggleable row per sub-task in
        ``questRequirementCheckerList``. Each row's checkbox is wired to
        :func:`mark_subtask_complete` /
        :func:`mark_subtask_incomplete` via
        :meth:`_on_subtask_toggled`.
        """
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

        # Sub-task progress label — updates as checkboxes toggle
        reqs = quest.get("questRequirementCheckerList")
        has_reqs = isinstance(reqs, list) and len(reqs) > 0
        if not has_reqs:
            progress_text = "No sub-tasks"
        else:
            done = sum(
                1
                for r in reqs
                if isinstance(r, dict) and r.get("complete") is True
            )
            progress_text = f"Sub-tasks: {done} / {len(reqs)} complete"
        progress = QLabel(progress_text)
        progress.setStyleSheet(_STATUS_QSS)
        col.addWidget(progress)

        # One checkbox row per sub-task
        subtasks: list[_SubTaskRow] = []
        if has_reqs:
            entry_index = len(self._quest_entries)
            for i, checker in enumerate(reqs):
                if not isinstance(checker, dict):
                    continue
                subtasks.append(
                    self._add_subtask_row(col, entry_index, i, checker)
                )

        # Append before the trailing stretch
        last = self._quest_list_layout.count() - 1
        self._quest_list_layout.insertWidget(last, frame)
        self._quest_entries.append(
            _QuestEntry(
                frame=frame,
                quest=quest,
                subtasks=subtasks,
                progress_label=progress,
            )
        )

    def _add_subtask_row(
        self,
        parent_layout: QVBoxLayout,
        entry_index: int,
        sub_task_index: int,
        checker: dict[str, Any],
    ) -> _SubTaskRow:
        """Build one sub-task row (checkbox + requirement text) and wire it up.

        The checkbox's ``stateChanged`` signal is bound (via lambda with
        captured indices) to :meth:`_on_subtask_toggled`, so the handler
        can locate the right :class:`_QuestEntry` and the right checker
        dict without scanning.
        """
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()
        checkbox.setChecked(checker.get("complete") is True)
        row.addWidget(checkbox, 0, Qt.AlignTop)

        text = str(
            checker.get("requirementText") or checker.get("prefixText") or ""
        ).rstrip("\t")
        label = QLabel(_render_requirement_text(text))
        label.setStyleSheet(_STATUS_QSS)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(label, 1)

        parent_layout.addLayout(row)

        checkbox.stateChanged.connect(
            lambda _state, e=entry_index, i=sub_task_index: self._on_subtask_toggled(
                e, i
            )
        )
        return _SubTaskRow(checkbox=checkbox, label=label, checker=checker)

    def _on_subtask_toggled(self, entry_index: int, sub_task_index: int) -> None:
        """Mark a single sub-task complete/incomplete and refresh the label.

        Mutates ``self._save.active_quest_list[entry_index]`` in place
        (via :func:`mark_subtask_complete` /
        :func:`mark_subtask_incomplete`), which flips the checker's
        ``complete`` flag and bumps the underlying ``CURRENT_X`` progress
        value to ``TARGET_X`` so the game treats the sub-task as
        actually done.
        """
        if entry_index < 0 or entry_index >= len(self._quest_entries):
            return
        entry = self._quest_entries[entry_index]
        if sub_task_index < 0 or sub_task_index >= len(entry.subtasks):
            return
        sub = entry.subtasks[sub_task_index]
        if sub.checkbox.isChecked():
            mark_subtask_complete(sub.checker, entry.quest, sub_task_index)
        else:
            mark_subtask_incomplete(sub.checker)
        # Refresh the per-entry progress counter
        reqs = entry.quest.get("questRequirementCheckerList")
        if isinstance(reqs, list) and reqs:
            done = sum(
                1
                for r in reqs
                if isinstance(r, dict) and r.get("complete") is True
            )
            entry.progress_label.setText(
                f"Sub-tasks: {done} / {len(reqs)} complete"
            )

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
                "Enter a save file path in the field above, or use "
                "Browse File… / Browse Folder….",
            )
            return
        path = Path(text).expanduser()
        if not path.exists():
            QMessageBox.critical(self, "Error", f"File not found:\n{path}")
            return
        self.load_from_path(path)

    def _on_browse_folder(self) -> None:
        """Open a directory picker to choose the save folder.

        Uses ``QFileDialog.getExistingDirectory`` (the directory-only
        variant of the standard file dialog) so the user can navigate
        to deep Wine prefix paths without typing them by hand. On
        accept, the folder field is updated and the slot combo is
        rescanned.
        """
        start = self._folder_path_edit.text().strip() or str(default_save_dir())
        folder_str = QFileDialog.getExistingDirectory(
            self,
            "Select Save Folder",
            start,
            QFileDialog.ShowDirsOnly,
        )
        if not folder_str:
            return
        self._folder_path_edit.setText(folder_str)
        self._rescan_folder(Path(folder_str))

    def _on_folder_changed(self) -> None:
        """Rescan the folder field's path and repopulate the slot combo.

        Triggered on Enter inside the folder field (the user just
        pasted a path) and on focus-out. An empty field clears the
        combo; a non-existent path is left empty with the status label
        set to ``0 slots`` rather than raising — the user is still
        typing.
        """
        text = self._folder_path_edit.text().strip()
        if not text:
            self._rescan_folder(None)
            return
        self._rescan_folder(Path(text).expanduser())

    def _on_slot_changed(self, index: int) -> None:
        """Copy the selected slot's full path into the file path field.

        We don't auto-load — the user has to click ``Load`` to confirm.
        That keeps the load flow single-source (the file field + the
        ``_on_load_path`` handler) and avoids loading a save the user
        just glanced at.
        """
        if index < 0:
            return
        full_path = self._slot_combo.itemData(index)
        if full_path:
            self._path_edit.setText(full_path)

    def _rescan_folder(self, folder: Path | None) -> None:
        """Populate the slot combo with ``*.rjson`` files in ``folder``.

        Behaviour:
          * ``folder is None`` or path doesn't exist or isn't a directory:
            combo is cleared and disabled, status shows ``0 slots``.
          * folder exists but has no ``*.rjson`` files: combo shows a
            single disabled placeholder, status shows ``0 slots``.
          * folder has saves: one combo item per ``*.rjson`` (sorted),
            full path stashed in ``userData``; status shows ``N slots``.

        Plain ``.json`` files (editor exports) are intentionally
        excluded — they're not save slots the game recognises.
        """
        self._slot_combo.blockSignals(True)
        self._slot_combo.clear()
        if folder is None or not folder.is_dir():
            self._slot_combo.setEnabled(False)
            self._folder_status.setText("0 slots")
            self._slot_combo.blockSignals(False)
            return
        saves = sorted(folder.glob(f"*{RJSON_SUFFIX}"))
        if not saves:
            self._slot_combo.addItem("(no saves in this folder)", userData=None)
            self._slot_combo.setEnabled(False)
            self._folder_status.setText("0 slots")
            self._slot_combo.blockSignals(False)
            return
        for save in saves:
            self._slot_combo.addItem(save.name, userData=str(save))
        self._slot_combo.setEnabled(True)
        count = len(saves)
        self._folder_status.setText(f"{count} slot{'s' if count != 1 else ''}")
        self._slot_combo.blockSignals(False)

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
