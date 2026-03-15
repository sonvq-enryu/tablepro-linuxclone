"""Centralized color scheme definitions for themed UI rendering."""

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
    sidebar_schema: QColor
    sidebar_table: QColor
    sidebar_column: QColor
    sidebar_pk: QColor
    sidebar_loading: QColor
    selected_bg: QColor
    selected_text: QColor
    item_text: QColor
    edit_bg: QColor
    insert_bg: QColor
    delete_bg: QColor


@dataclass(frozen=True)
class ColorScheme:
    """Complete scheme containing Python tokens and QSS placeholders."""

    id: str
    name: str
    is_dark: bool
    colors: ThemeColors
    qss: dict[str, str]


def _q(hex_color: str) -> QColor:
    return QColor(hex_color)


CATPPUCCIN_MOCHA = ColorScheme(
    id="catppuccin_mocha",
    name="Catppuccin Mocha",
    is_dark=True,
    colors=ThemeColors(
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
        sidebar_schema=_q("#89b4fa"),
        sidebar_table=_q("#a6e3a1"),
        sidebar_column=_q("#a6adc8"),
        sidebar_pk=_q("#fab387"),
        sidebar_loading=_q("#6c7086"),
        selected_bg=_q("#1e293b"),
        selected_text=_q("#ffffff"),
        item_text=_q("#e2e8f0"),
        edit_bg=QColor(249, 226, 175, 38),
        insert_bg=QColor(166, 227, 161, 38),
        delete_bg=QColor(243, 139, 168, 25),
    ),
    qss={
        "base": "#1e1e2e",
        "surface": "#181825",
        "deep": "#11111b",
        "overlay": "#313244",
        "border": "#45475a",
        "hover": "#252738",
        "pressed": "#2d2f42",
        "input_bg": "#1a1a27",
        "input_hover": "#2b2b3a",
        "primary": "#22c55e",
        "primary_hover": "#16a34a",
        "primary_pressed": "#15803d",
        "primary_deep": "#2f6f45",
        "secondary": "#89b4fa",
        "error": "#f38ba8",
        "warning": "#fab387",
        "warning_strong": "#fbbf24",
        "splitter_pressed": "#74c7ec",
        "text": "#cdd6f4",
        "subtext": "#a6adc8",
        "subtext_soft": "#7f849c",
        "muted": "#6c7086",
        "faint": "#585b70",
        "success_soft": "#9db6a8",
        "tab_active": "#1e293b",
        "white": "#ffffff",
        "selection_rgba": "rgba(203, 166, 247, 0.15)",
        "selection_rgba_strong": "rgba(203, 166, 247, 0.2)",
        "warning_rgba": "rgba(250, 179, 135, 0.12)",
    },
)

LIGHT = ColorScheme(
    id="light",
    name="Light",
    is_dark=False,
    colors=ThemeColors(
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
        sidebar_schema=_q("#2563eb"),
        sidebar_table=_q("#16a34a"),
        sidebar_column=_q("#64748b"),
        sidebar_pk=_q("#b45309"),
        sidebar_loading=_q("#94a3b8"),
        selected_bg=_q("#dcfce7"),
        selected_text=_q("#16a34a"),
        item_text=_q("#334155"),
        edit_bg=QColor(250, 204, 21, 30),
        insert_bg=QColor(34, 197, 94, 30),
        delete_bg=QColor(239, 68, 68, 20),
    ),
    qss={
        "base": "#ffffff",
        "surface": "#ffffff",
        "deep": "#f8fafc",
        "overlay": "#e2e8f0",
        "border": "#cbd5e1",
        "hover": "#f1f5f9",
        "pressed": "#e2e8f0",
        "input_bg": "#ffffff",
        "input_hover": "#f8fafc",
        "primary": "#22c55e",
        "primary_hover": "#16a34a",
        "primary_pressed": "#15803d",
        "primary_deep": "#86b89a",
        "secondary": "#3b82f6",
        "error": "#ef4444",
        "warning": "#f97316",
        "warning_strong": "#f59e0b",
        "splitter_pressed": "#16a34a",
        "text": "#1e293b",
        "subtext": "#334155",
        "subtext_soft": "#64748b",
        "muted": "#64748b",
        "faint": "#94a3b8",
        "success_soft": "#10b981",
        "tab_active": "#ddd6fe",
        "white": "#ffffff",
        "selection_rgba": "rgba(139, 92, 246, 0.1)",
        "selection_rgba_strong": "rgba(139, 92, 246, 0.15)",
        "warning_rgba": "rgba(251, 191, 36, 0.2)",
    },
)

DRACULA = ColorScheme(
    id="dracula",
    name="Dracula",
    is_dark=True,
    colors=ThemeColors(
        base=_q("#282a36"),
        surface=_q("#21222c"),
        overlay=_q("#44475a"),
        text=_q("#f8f8f2"),
        subtext=_q("#d6d6cf"),
        muted=_q("#8b92b2"),
        faint=_q("#6272a4"),
        primary=_q("#50fa7b"),
        primary_hover=_q("#3ee66b"),
        secondary=_q("#bd93f9"),
        error=_q("#ff5555"),
        warning=_q("#ffb86c"),
        success=_q("#50fa7b"),
        info=_q("#8be9fd"),
        syn_keyword=_q("#ff79c6"),
        syn_datatype=_q("#f1fa8c"),
        syn_function=_q("#8be9fd"),
        syn_string=_q("#f1fa8c"),
        syn_number=_q("#bd93f9"),
        syn_comment=_q("#6272a4"),
        syn_operator=_q("#ff79c6"),
        gutter=_q("#21222c"),
        current_line=_q("#343746"),
        line_num=_q("#6272a4"),
        line_num_active=_q("#f8f8f2"),
        badge_bg=_q("#383a59"),
        badge_text=_q("#bd93f9"),
        sidebar_schema=_q("#8be9fd"),
        sidebar_table=_q("#50fa7b"),
        sidebar_column=_q("#d6d6cf"),
        sidebar_pk=_q("#ffb86c"),
        sidebar_loading=_q("#8b92b2"),
        selected_bg=_q("#383a59"),
        selected_text=_q("#f8f8f2"),
        item_text=_q("#f2f2ed"),
        edit_bg=QColor(241, 250, 140, 36),
        insert_bg=QColor(80, 250, 123, 34),
        delete_bg=QColor(255, 85, 85, 28),
    ),
    qss={
        "base": "#282a36",
        "surface": "#21222c",
        "deep": "#1f1f28",
        "overlay": "#44475a",
        "border": "#6272a4",
        "hover": "#343746",
        "pressed": "#3b3f57",
        "input_bg": "#1f222d",
        "input_hover": "#282d3a",
        "primary": "#50fa7b",
        "primary_hover": "#3ee66b",
        "primary_pressed": "#2fc45a",
        "primary_deep": "#2f6f45",
        "secondary": "#bd93f9",
        "error": "#ff5555",
        "warning": "#ffb86c",
        "warning_strong": "#f1fa8c",
        "splitter_pressed": "#8be9fd",
        "text": "#f8f8f2",
        "subtext": "#d6d6cf",
        "subtext_soft": "#bdc0d3",
        "muted": "#8b92b2",
        "faint": "#6272a4",
        "success_soft": "#8ad4a4",
        "tab_active": "#2b2f45",
        "white": "#ffffff",
        "selection_rgba": "rgba(189, 147, 249, 0.15)",
        "selection_rgba_strong": "rgba(189, 147, 249, 0.25)",
        "warning_rgba": "rgba(255, 184, 108, 0.12)",
    },
)

NORD = ColorScheme(
    id="nord",
    name="Nord",
    is_dark=True,
    colors=ThemeColors(
        base=_q("#2e3440"),
        surface=_q("#3b4252"),
        overlay=_q("#434c5e"),
        text=_q("#e5e9f0"),
        subtext=_q("#d8dee9"),
        muted=_q("#8c96aa"),
        faint=_q("#6c788f"),
        primary=_q("#a3be8c"),
        primary_hover=_q("#b3cb9a"),
        secondary=_q("#81a1c1"),
        error=_q("#bf616a"),
        warning=_q("#d08770"),
        success=_q("#a3be8c"),
        info=_q("#88c0d0"),
        syn_keyword=_q("#b48ead"),
        syn_datatype=_q("#ebcb8b"),
        syn_function=_q("#88c0d0"),
        syn_string=_q("#a3be8c"),
        syn_number=_q("#d08770"),
        syn_comment=_q("#6c788f"),
        syn_operator=_q("#81a1c1"),
        gutter=_q("#3b4252"),
        current_line=_q("#3f4658"),
        line_num=_q("#6c788f"),
        line_num_active=_q("#e5e9f0"),
        badge_bg=_q("#4c566a"),
        badge_text=_q("#88c0d0"),
        sidebar_schema=_q("#81a1c1"),
        sidebar_table=_q("#a3be8c"),
        sidebar_column=_q("#d8dee9"),
        sidebar_pk=_q("#ebcb8b"),
        sidebar_loading=_q("#8c96aa"),
        selected_bg=_q("#4c566a"),
        selected_text=_q("#eceff4"),
        item_text=_q("#e5e9f0"),
        edit_bg=QColor(235, 203, 139, 34),
        insert_bg=QColor(163, 190, 140, 32),
        delete_bg=QColor(191, 97, 106, 28),
    ),
    qss={
        "base": "#2e3440",
        "surface": "#3b4252",
        "deep": "#2b303b",
        "overlay": "#434c5e",
        "border": "#4c566a",
        "hover": "#3f4658",
        "pressed": "#4c566a",
        "input_bg": "#2b303b",
        "input_hover": "#3f4658",
        "primary": "#a3be8c",
        "primary_hover": "#b3cb9a",
        "primary_pressed": "#8ea979",
        "primary_deep": "#70875f",
        "secondary": "#81a1c1",
        "error": "#bf616a",
        "warning": "#d08770",
        "warning_strong": "#ebcb8b",
        "splitter_pressed": "#88c0d0",
        "text": "#e5e9f0",
        "subtext": "#d8dee9",
        "subtext_soft": "#c8d0de",
        "muted": "#8c96aa",
        "faint": "#6c788f",
        "success_soft": "#9bb58d",
        "tab_active": "#434c5e",
        "white": "#ffffff",
        "selection_rgba": "rgba(129, 161, 193, 0.16)",
        "selection_rgba_strong": "rgba(129, 161, 193, 0.26)",
        "warning_rgba": "rgba(235, 203, 139, 0.14)",
    },
)

SOLARIZED_DARK = ColorScheme(
    id="solarized_dark",
    name="Solarized Dark",
    is_dark=True,
    colors=ThemeColors(
        base=_q("#002b36"),
        surface=_q("#073642"),
        overlay=_q("#094352"),
        text=_q("#93a1a1"),
        subtext=_q("#839496"),
        muted=_q("#657b83"),
        faint=_q("#586e75"),
        primary=_q("#859900"),
        primary_hover=_q("#93a900"),
        secondary=_q("#268bd2"),
        error=_q("#dc322f"),
        warning=_q("#cb4b16"),
        success=_q("#859900"),
        info=_q("#2aa198"),
        syn_keyword=_q("#6c71c4"),
        syn_datatype=_q("#b58900"),
        syn_function=_q("#268bd2"),
        syn_string=_q("#859900"),
        syn_number=_q("#d33682"),
        syn_comment=_q("#586e75"),
        syn_operator=_q("#2aa198"),
        gutter=_q("#073642"),
        current_line=_q("#0b3a44"),
        line_num=_q("#586e75"),
        line_num_active=_q("#93a1a1"),
        badge_bg=_q("#0b3a44"),
        badge_text=_q("#2aa198"),
        sidebar_schema=_q("#268bd2"),
        sidebar_table=_q("#859900"),
        sidebar_column=_q("#839496"),
        sidebar_pk=_q("#b58900"),
        sidebar_loading=_q("#657b83"),
        selected_bg=_q("#17515f"),
        selected_text=_q("#fdf6e3"),
        item_text=_q("#93a1a1"),
        edit_bg=QColor(181, 137, 0, 38),
        insert_bg=QColor(133, 153, 0, 32),
        delete_bg=QColor(220, 50, 47, 30),
    ),
    qss={
        "base": "#002b36",
        "surface": "#073642",
        "deep": "#001f27",
        "overlay": "#094352",
        "border": "#586e75",
        "hover": "#0b3a44",
        "pressed": "#17515f",
        "input_bg": "#002731",
        "input_hover": "#0b3a44",
        "primary": "#859900",
        "primary_hover": "#93a900",
        "primary_pressed": "#6e8200",
        "primary_deep": "#556a00",
        "secondary": "#268bd2",
        "error": "#dc322f",
        "warning": "#cb4b16",
        "warning_strong": "#b58900",
        "splitter_pressed": "#2aa198",
        "text": "#93a1a1",
        "subtext": "#839496",
        "subtext_soft": "#7b8b8d",
        "muted": "#657b83",
        "faint": "#586e75",
        "success_soft": "#8ca860",
        "tab_active": "#003846",
        "white": "#ffffff",
        "selection_rgba": "rgba(38, 139, 210, 0.18)",
        "selection_rgba_strong": "rgba(38, 139, 210, 0.28)",
        "warning_rgba": "rgba(181, 137, 0, 0.16)",
    },
)

TOKYO_NIGHT = ColorScheme(
    id="tokyo_night",
    name="Tokyo Night",
    is_dark=True,
    colors=ThemeColors(
        base=_q("#1a1b26"),
        surface=_q("#1f2335"),
        overlay=_q("#2f3549"),
        text=_q("#c0caf5"),
        subtext=_q("#a9b1d6"),
        muted=_q("#737aa2"),
        faint=_q("#565f89"),
        primary=_q("#9ece6a"),
        primary_hover=_q("#8fd35f"),
        secondary=_q("#7aa2f7"),
        error=_q("#f7768e"),
        warning=_q("#ff9e64"),
        success=_q("#9ece6a"),
        info=_q("#73daca"),
        syn_keyword=_q("#bb9af7"),
        syn_datatype=_q("#e0af68"),
        syn_function=_q("#7aa2f7"),
        syn_string=_q("#9ece6a"),
        syn_number=_q("#ff9e64"),
        syn_comment=_q("#565f89"),
        syn_operator=_q("#73daca"),
        gutter=_q("#1f2335"),
        current_line=_q("#24283b"),
        line_num=_q("#565f89"),
        line_num_active=_q("#c0caf5"),
        badge_bg=_q("#2a3046"),
        badge_text=_q("#7aa2f7"),
        sidebar_schema=_q("#7aa2f7"),
        sidebar_table=_q("#9ece6a"),
        sidebar_column=_q("#a9b1d6"),
        sidebar_pk=_q("#e0af68"),
        sidebar_loading=_q("#737aa2"),
        selected_bg=_q("#414868"),
        selected_text=_q("#c0caf5"),
        item_text=_q("#c0caf5"),
        edit_bg=QColor(224, 175, 104, 36),
        insert_bg=QColor(158, 206, 106, 32),
        delete_bg=QColor(247, 118, 142, 28),
    ),
    qss={
        "base": "#1a1b26",
        "surface": "#1f2335",
        "deep": "#16161e",
        "overlay": "#2f3549",
        "border": "#414868",
        "hover": "#2a3046",
        "pressed": "#3b4261",
        "input_bg": "#161923",
        "input_hover": "#24283b",
        "primary": "#9ece6a",
        "primary_hover": "#8fd35f",
        "primary_pressed": "#73b04f",
        "primary_deep": "#2f5f3a",
        "secondary": "#7aa2f7",
        "error": "#f7768e",
        "warning": "#ff9e64",
        "warning_strong": "#e0af68",
        "splitter_pressed": "#73daca",
        "text": "#c0caf5",
        "subtext": "#a9b1d6",
        "subtext_soft": "#9aa5ce",
        "muted": "#737aa2",
        "faint": "#565f89",
        "success_soft": "#a9dc76",
        "tab_active": "#24283b",
        "white": "#ffffff",
        "selection_rgba": "rgba(122, 162, 247, 0.18)",
        "selection_rgba_strong": "rgba(122, 162, 247, 0.28)",
        "warning_rgba": "rgba(224, 175, 104, 0.15)",
    },
)

GRUVBOX_DARK = ColorScheme(
    id="gruvbox_dark",
    name="Gruvbox Dark",
    is_dark=True,
    colors=ThemeColors(
        base=_q("#282828"),
        surface=_q("#32302f"),
        overlay=_q("#3c3836"),
        text=_q("#ebdbb2"),
        subtext=_q("#d5c4a1"),
        muted=_q("#a89984"),
        faint=_q("#928374"),
        primary=_q("#98971a"),
        primary_hover=_q("#b8bb26"),
        secondary=_q("#83a598"),
        error=_q("#fb4934"),
        warning=_q("#fe8019"),
        success=_q("#b8bb26"),
        info=_q("#8ec07c"),
        syn_keyword=_q("#d3869b"),
        syn_datatype=_q("#fabd2f"),
        syn_function=_q("#83a598"),
        syn_string=_q("#b8bb26"),
        syn_number=_q("#d65d0e"),
        syn_comment=_q("#928374"),
        syn_operator=_q("#8ec07c"),
        gutter=_q("#32302f"),
        current_line=_q("#3a3735"),
        line_num=_q("#928374"),
        line_num_active=_q("#ebdbb2"),
        badge_bg=_q("#504945"),
        badge_text=_q("#83a598"),
        sidebar_schema=_q("#83a598"),
        sidebar_table=_q("#b8bb26"),
        sidebar_column=_q("#d5c4a1"),
        sidebar_pk=_q("#fabd2f"),
        sidebar_loading=_q("#a89984"),
        selected_bg=_q("#504945"),
        selected_text=_q("#fbf1c7"),
        item_text=_q("#ebdbb2"),
        edit_bg=QColor(250, 189, 47, 36),
        insert_bg=QColor(184, 187, 38, 32),
        delete_bg=QColor(251, 73, 52, 28),
    ),
    qss={
        "base": "#282828",
        "surface": "#32302f",
        "deep": "#1d2021",
        "overlay": "#3c3836",
        "border": "#504945",
        "hover": "#3a3735",
        "pressed": "#4b443f",
        "input_bg": "#1f1f1f",
        "input_hover": "#2a2827",
        "primary": "#98971a",
        "primary_hover": "#b8bb26",
        "primary_pressed": "#79740e",
        "primary_deep": "#4f5b16",
        "secondary": "#83a598",
        "error": "#fb4934",
        "warning": "#fe8019",
        "warning_strong": "#fabd2f",
        "splitter_pressed": "#8ec07c",
        "text": "#ebdbb2",
        "subtext": "#d5c4a1",
        "subtext_soft": "#bdae93",
        "muted": "#a89984",
        "faint": "#928374",
        "success_soft": "#b8bb26",
        "tab_active": "#3a3735",
        "white": "#ffffff",
        "selection_rgba": "rgba(131, 165, 152, 0.18)",
        "selection_rgba_strong": "rgba(131, 165, 152, 0.28)",
        "warning_rgba": "rgba(250, 189, 47, 0.16)",
    },
)

SCHEMES: dict[str, ColorScheme] = {
    scheme.id: scheme
    for scheme in (
        CATPPUCCIN_MOCHA,
        LIGHT,
        DRACULA,
        NORD,
        SOLARIZED_DARK,
        TOKYO_NIGHT,
        GRUVBOX_DARK,
    )
}

_current_scheme = CATPPUCCIN_MOCHA


def current() -> ThemeColors:
    """Return the currently active theme token set."""
    return _current_scheme.colors


def current_scheme() -> ColorScheme:
    """Return the active color scheme metadata."""
    return _current_scheme


def schemes() -> list[ColorScheme]:
    """Return available color schemes in UI order."""
    return list(SCHEMES.values())


def set_scheme(scheme_id: str) -> None:
    """Activate a scheme by ID."""
    global _current_scheme
    try:
        _current_scheme = SCHEMES[scheme_id]
    except KeyError as exc:
        raise ValueError(f"Unknown color scheme: {scheme_id}") from exc


def set_dark() -> None:
    """Backward-compatible dark scheme activator."""
    set_scheme(CATPPUCCIN_MOCHA.id)


def set_light() -> None:
    """Backward-compatible light scheme activator."""
    set_scheme(LIGHT.id)
