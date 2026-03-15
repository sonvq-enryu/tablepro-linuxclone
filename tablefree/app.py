"""Application factory — creates and configures the QApplication."""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from tablefree.resource_path import resources_dir


def create_app(argv: list[str] | None = None) -> QApplication:
    """Create and configure the QApplication instance."""
    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    app.setApplicationName("TableFree")
    app.setOrganizationName("TableFree")
    app.setApplicationVersion("0.1.0")

    icon_path = resources_dir() / "icons" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    return app
