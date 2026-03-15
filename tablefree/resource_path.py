"""Helpers for locating bundled resources in dev and frozen builds."""

import sys
from pathlib import Path


def resources_dir() -> Path:
    """Return the resources directory for source or PyInstaller runtime."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "resources"
    return Path(__file__).resolve().parent.parent / "resources"
