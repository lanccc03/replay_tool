from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


COLORS = {
    "app_background": "#F6F7F9",
    "surface": "#FFFFFF",
    "surface_muted": "#EEF2F5",
    "border": "#D8DEE6",
    "text_primary": "#1F2933",
    "text_secondary": "#667085",
    "text_disabled": "#98A2B3",
    "primary": "#087F8C",
    "primary_hover": "#066C77",
    "primary_subtle": "#DDF4F2",
    "link": "#3B5BDB",
    "success": "#178C55",
    "warning": "#B7791F",
    "danger": "#C2410C",
    "running": "#0E7490",
    "focus": "#7DD3FC",
}


def apply_theme(app: QApplication) -> None:
    """Apply the default light engineering theme to a QApplication.

    Args:
        app: Qt application instance to style.
    """
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(_stylesheet())


def monospace_font(point_size: int = 9) -> QFont:
    """Return the standard monospace font used for IDs and timestamps.

    Args:
        point_size: Desired font point size.

    Returns:
        A configured QFont instance.
    """
    font = QFont("Consolas", point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def _stylesheet() -> str:
    return """
QMainWindow {
    background: #F6F7F9;
    color: #1F2933;
}
QFrame#TopStatusBar, QFrame#InspectorPanel, QFrame#NavigationPanel {
    background: #FFFFFF;
    border: 1px solid #D8DEE6;
}
QFrame#ContentPanel {
    background: #FFFFFF;
    border: 1px solid #D8DEE6;
}
QFrame#ToolbarHeader {
    background: #EEF2F5;
    border: none;
    border-bottom: 1px solid #D8DEE6;
}
QLabel#StatusPill {
    background: #DDF4F2;
    border: 1px solid #087F8C;
    border-radius: 6px;
    color: #087F8C;
    padding: 3px 8px;
}
QListWidget {
    background: #FFFFFF;
    border: none;
    outline: none;
}
QListWidget::item {
    border-radius: 6px;
    margin: 2px 6px;
    padding: 8px 10px;
}
QListWidget::item:selected {
    background: #DDF4F2;
    color: #087F8C;
}
QPushButton {
    background: #FFFFFF;
    border: 1px solid #D8DEE6;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton:hover {
    border-color: #087F8C;
}
QPushButton:disabled {
    color: #98A2B3;
    background: #EEF2F5;
}
QPushButton[primary="true"] {
    background: #087F8C;
    border-color: #087F8C;
    color: #FFFFFF;
}
QPushButton[primary="true"]:hover {
    background: #066C77;
}
QTableView {
    background: #FFFFFF;
    alternate-background-color: #F6F7F9;
    border: 1px solid #D8DEE6;
    gridline-color: #D8DEE6;
    selection-background-color: #DDF4F2;
    selection-color: #1F2933;
}
QHeaderView::section {
    background: #EEF2F5;
    border: none;
    border-right: 1px solid #D8DEE6;
    border-bottom: 1px solid #D8DEE6;
    padding: 6px;
    color: #667085;
}
QLineEdit, QSpinBox, QComboBox, QTextEdit {
    background: #FFFFFF;
    border: 1px solid #D8DEE6;
    border-radius: 6px;
    padding: 5px 7px;
}
QSplitter::handle {
    background: #D8DEE6;
}
"""

