"""Application factory — creates and configures the QApplication."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

_ROOT = Path(__file__).resolve().parent.parent
_RESOURCES = _ROOT / "resources"


def create_app(argv: list[str] | None = None) -> QApplication:
    """Create and configure the QApplication instance."""
    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    app.setApplicationName("TableFree")
    app.setOrganizationName("TableFree")
    app.setApplicationVersion("0.1.0")

    icon_path = _RESOURCES / "icons" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    return app
