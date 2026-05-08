from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from replay_tool.app import ReplayApplication
from replay_ui_qt.app_context import AppContext
from replay_ui_qt.main_window import MainWindow
from replay_ui_qt.theme import apply_theme


def main(argv: list[str] | None = None) -> int:
    """Run the next_replay PySide6 workbench.

    Args:
        argv: Optional command argument list. When None, sys.argv is used.

    Returns:
        Qt process exit code.
    """
    parser = argparse.ArgumentParser(prog="replay-ui")
    parser.add_argument("--workspace", default=".replay_tool", help="Trace/project workspace directory.")
    args = parser.parse_args(argv)

    qt_args = [sys.argv[0] if sys.argv else "replay-ui"]
    app = QApplication(qt_args)
    apply_theme(app)

    workspace = Path(args.workspace)
    replay_app = ReplayApplication(workspace=workspace)
    context = AppContext(workspace=workspace, application=replay_app)
    window = MainWindow(context)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())

