"""``ppse gui`` — launch the PySide6 save editor window.

The GUI is implemented in :mod:`permit_save_editor.ui.main_window`. This
module is the thin entry point that wires the typer command to it.

Importing the heavy PySide6 stack is deferred to the ``run_gui`` call so
that headless commands (``inspect``, ``set``, ``unlock``) don't pay the
import cost.
"""

from __future__ import annotations

from pathlib import Path


def run_gui(initial_path: Path | None = None) -> None:
    """Launch the GUI. Blocks until the user closes the window.

    Set the ``QT_QPA_PLATFORM=offscreen`` environment variable to run
    headless (used by the smoke test).
    """
    from PySide6.QtWidgets import QApplication

    from ..ui.main_window import MainWindow
    from ..ui.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow()
    window.show()
    if initial_path is not None:
        window.load_from_path(initial_path)
    app.exec()
