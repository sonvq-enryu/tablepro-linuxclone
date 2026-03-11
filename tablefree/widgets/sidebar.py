"""Sidebar widget — Schema browser placeholder with search and tree structure."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QWidget):
    """Left panel: schema tree browser with search filter (placeholder)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar-panel")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header with title ────────────────────────────────
        header = QWidget()
        header.setObjectName("sidebar-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)

        title = QLabel("Schema Browser")
        title.setObjectName("sidebar-title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Connection badge
        badge = QLabel("● Disconnected")
        badge.setObjectName("connection-badge-inactive")
        header_layout.addWidget(badge)

        layout.addWidget(header)

        # ── Search bar ───────────────────────────────────────
        search_container = QWidget()
        search_container.setObjectName("search-container")
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 6, 8, 6)

        self._search = QLineEdit()
        self._search.setObjectName("sidebar-search")
        self._search.setPlaceholderText("🔍  Filter objects…")
        self._search.setClearButtonEnabled(True)
        search_layout.addWidget(self._search)

        layout.addWidget(search_container)

        # ── Separator ────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("sidebar-separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ── Tree view (placeholder structure) ────────────────
        self._tree = QTreeWidget()
        self._tree.setObjectName("schema-tree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setRootIsDecorated(True)

        # Populate placeholder items
        self._populate_placeholder_tree()

        layout.addWidget(self._tree, stretch=1)

        # ── Footer info ──────────────────────────────────────
        footer = QLabel("Connect to a database to browse schema")
        footer.setObjectName("sidebar-footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

    def _populate_placeholder_tree(self) -> None:
        """Add sample tree structure to show the layout."""
        categories = {
            "📁  Tables": ["users", "orders", "products", "categories"],
            "👁  Views": ["active_users", "order_summary"],
            "⚡  Functions": ["calculate_total", "validate_email"],
            "📦  Procedures": ["sync_inventory", "generate_report"],
        }

        for category, items in categories.items():
            parent = QTreeWidgetItem(self._tree, [category])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for item_name in items:
                child = QTreeWidgetItem(parent, [f"  {item_name}"])
                child.setToolTip(0, item_name)

        # Expand first category to show it's interactive
        self._tree.expandItem(self._tree.topLevelItem(0))
