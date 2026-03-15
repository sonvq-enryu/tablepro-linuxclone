"""Centralized theme color definitions for runtime-painted widgets."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


@dataclass(frozen=True)
class ThemeColors:
    """Immutable color token set used by Python-rendered UI elements."""

    base: QColor
    surface: QColor
    overlay: QColor
    text: QColor
    subtext: QColor
    muted: QColor
    faint: QColor
    primary: QColor
    primary_hover: QColor
    secondary: QColor
    error: QColor
    warning: QColor
    success: QColor
    info: QColor
    syn_keyword: QColor
    syn_datatype: QColor
    syn_function: QColor
    syn_string: QColor
    syn_number: QColor
    syn_comment: QColor
    syn_operator: QColor
    gutter: QColor
    current_line: QColor
    line_num: QColor
    line_num_active: QColor
    badge_bg: QColor
    badge_text: QColor
    selected_bg: QColor
    selected_text: QColor
    item_text: QColor
    edit_bg: QColor
    insert_bg: QColor
    delete_bg: QColor


def _q(hex_color: str) -> QColor:
    return QColor(hex_color)


DARK = ThemeColors(
    base=_q("#1e1e2e"),
    surface=_q("#181825"),
    overlay=_q("#313244"),
    text=_q("#cdd6f4"),
    subtext=_q("#a6adc8"),
    muted=_q("#6c7086"),
    faint=_q("#585b70"),
    primary=_q("#22c55e"),
    primary_hover=_q("#16a34a"),
    secondary=_q("#89b4fa"),
    error=_q("#f38ba8"),
    warning=_q("#fab387"),
    success=_q("#a6e3a1"),
    info=_q("#89dceb"),
    syn_keyword=_q("#cba6f7"),
    syn_datatype=_q("#f9e2af"),
    syn_function=_q("#89b4fa"),
    syn_string=_q("#a6e3a1"),
    syn_number=_q("#fab387"),
    syn_comment=_q("#6c7086"),
    syn_operator=_q("#89dceb"),
    gutter=_q("#181825"),
    current_line=_q("#242438"),
    line_num=_q("#585b70"),
    line_num_active=_q("#cdd6f4"),
    badge_bg=_q("#334155"),
    badge_text=_q("#93c5fd"),
    selected_bg=_q("#1e293b"),
    selected_text=_q("#ffffff"),
    item_text=_q("#e2e8f0"),
    edit_bg=QColor(249, 226, 175, 38),
    insert_bg=QColor(166, 227, 161, 38),
    delete_bg=QColor(243, 139, 168, 25),
)

LIGHT = ThemeColors(
    base=_q("#ffffff"),
    surface=_q("#f8fafc"),
    overlay=_q("#e2e8f0"),
    text=_q("#1e293b"),
    subtext=_q("#334155"),
    muted=_q("#64748b"),
    faint=_q("#94a3b8"),
    primary=_q("#22c55e"),
    primary_hover=_q("#16a34a"),
    secondary=_q("#3b82f6"),
    error=_q("#ef4444"),
    warning=_q("#f97316"),
    success=_q("#16a34a"),
    info=_q("#0ea5e9"),
    syn_keyword=_q("#7c3aed"),
    syn_datatype=_q("#b45309"),
    syn_function=_q("#2563eb"),
    syn_string=_q("#16a34a"),
    syn_number=_q("#c2410c"),
    syn_comment=_q("#94a3b8"),
    syn_operator=_q("#0891b2"),
    gutter=_q("#f8fafc"),
    current_line=_q("#f1f5f9"),
    line_num=_q("#94a3b8"),
    line_num_active=_q("#1e293b"),
    badge_bg=_q("#e2e8f0"),
    badge_text=_q("#3b82f6"),
    selected_bg=_q("#dcfce7"),
    selected_text=_q("#16a34a"),
    item_text=_q("#334155"),
    edit_bg=QColor(250, 204, 21, 30),
    insert_bg=QColor(34, 197, 94, 30),
    delete_bg=QColor(239, 68, 68, 20),
)

_current = DARK


def current() -> ThemeColors:
    """Return the currently active theme token set."""
    return _current


def set_dark() -> None:
    """Activate dark palette."""
    global _current
    _current = DARK


def set_light() -> None:
    """Activate light palette."""
    global _current
    _current = LIGHT
