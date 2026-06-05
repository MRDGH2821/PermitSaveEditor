"""Dark-theme stylesheet for the PySide6 UI.

Mirrors the original WPF theme (``#202020`` background, white text, accent
buttons). Applied once via :func:`apply_theme` before any widget is shown.
"""

from __future__ import annotations

# QSS — Qt's CSS-like stylesheet language. Subset of CSS2.1; uses Qt-specific
# selectors (`:hover`, `:pressed`, `:disabled`).
_DARK_QSS = """
QWidget {
    background-color: #202020;
    color: #ffffff;
    font-size: 10pt;
}

QMainWindow {
    background-color: #202020;
}

/* Buttons */
QPushButton {
    background-color: #2d2d30;
    color: #ffffff;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 18px;
}
QPushButton:hover { background-color: #3e3e42; }
QPushButton:pressed { background-color: #0078d7; }
QPushButton:disabled {
    background-color: #1f1f1f;
    color: #6a6a6a;
    border-color: #2d2d30;
}

/* Text inputs */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #252526;
    color: #ffffff;
    border: 1px solid #3f3f46;
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: #0078d7;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #0078d7;
}
QLineEdit:disabled, QSpinBox:disabled {
    color: #6a6a6a;
    background-color: #1f1f1f;
}

/* Tab widget */
QTabWidget::pane {
    border: 1px solid #3f3f46;
    background-color: #202020;
    top: -1px;
}
QTabBar::tab {
    background-color: #2d2d30;
    color: #cccccc;
    padding: 8px 18px;
    border: 1px solid #3f3f46;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #202020;
    color: #ffffff;
    border-bottom: 1px solid #202020;
}
QTabBar::tab:hover:!selected {
    background-color: #3e3e42;
}

/* Labels */
QLabel {
    color: #ffffff;
    background-color: transparent;
}

/* Radio buttons */
QRadioButton {
    color: #ffffff;
    spacing: 6px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid #6a6a6a;
    background-color: #252526;
}
QRadioButton::indicator:checked {
    background-color: #0078d7;
    border-color: #0078d7;
}

/* Scrollbars (slim, dark) */
QScrollBar:vertical {
    background: #1f1f1f;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #424242;
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #525252; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def apply_theme(app) -> None:  # type: ignore[no-untyped-def]
    """Apply the dark theme to a ``QApplication`` instance."""
    app.setStyle("Fusion")  # consistent cross-platform look
    app.setStyleSheet(_DARK_QSS)


__all__ = ["apply_theme"]
