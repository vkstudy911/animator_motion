#!/usr/bin/env python3
"""AI Doodle Studio — 2D Animation Desktop Application.

Entry point that creates the Qt application, applies the dark theme,
creates the main window, and starts the event loop.

Usage:
    python main.py [project_file.adsproj]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package root is importable when running from the ai_doodle_studio/ directory
_pkg_root = Path(__file__).resolve().parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.theme.styles import apply_dark_theme
from app.ui.main_window import MainWindow


def main() -> int:
    """Application entry point."""
    # Enable High-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Doodle Studio")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("AI Doodle Studio")

    # Apply dark theme
    apply_dark_theme(app)

    # Check for project file argument
    project_path = None
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if not candidate.startswith("-"):
            project_path = candidate

    # Create and show main window
    window = MainWindow(project_path=project_path)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
