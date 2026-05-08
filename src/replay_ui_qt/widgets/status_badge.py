from __future__ import annotations

from PySide6.QtWidgets import QLabel

from replay_ui_qt.theme import COLORS


STATUS_COLORS = {
    "ready": ("#DDF4F2", COLORS["success"]),
    "missing": ("#FFF7E6", COLORS["warning"]),
    "running": ("#E0F2FE", COLORS["running"]),
    "failed": ("#FEE4E2", COLORS["danger"]),
    "disabled": (COLORS["surface_muted"], COLORS["text_disabled"]),
    "default": (COLORS["surface_muted"], COLORS["text_secondary"]),
}


class StatusBadge(QLabel):
    """Small text badge that combines status text with semantic color."""

    def __init__(self, text: str = "", semantic: str = "default") -> None:
        """Create a status badge.

        Args:
            text: Visible badge text.
            semantic: Semantic color key such as ready, missing, running,
                failed, disabled, or default.
        """
        super().__init__()
        self.setObjectName("StatusBadge")
        self._semantic = "default"
        self.set_status(text, semantic)

    @property
    def semantic(self) -> str:
        """Return the current semantic state.

        Returns:
            Semantic color key.
        """
        return self._semantic

    def set_status(self, text: str, semantic: str = "default") -> None:
        """Update the badge text and semantic color.

        Args:
            text: Visible badge text.
            semantic: Semantic color key.
        """
        key = semantic if semantic in STATUS_COLORS else "default"
        background, foreground = STATUS_COLORS[key]
        self._semantic = key
        self.setText(str(text))
        self.setStyleSheet(
            "QLabel#StatusBadge {{ "
            "background: {background}; "
            "border: 1px solid {foreground}; "
            "border-radius: 6px; "
            "color: {foreground}; "
            "padding: 3px 8px; "
            "}}".format(background=background, foreground=foreground)
        )

