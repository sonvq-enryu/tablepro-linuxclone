"""Connection setup dialog - TablePlus style for software engineers."""

import re
from typing import Any

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tablefree.db.config import ConnectionConfig, DriverType
from tablefree.db.connection_store import ConnectionStore
from tablefree.db.driver import DatabaseDriver
from tablefree.db.manager import ConnectionManager
from tablefree.db.mysql_driver import MySQLDriver
from tablefree.db.postgres_driver import PostgreSQLDriver
from tablefree.workers import QueryWorker


class ConnectionDialog(QDialog):
    """Modal dialog for managing and establishing database connections.

    Features:
    - Quick Connect bar for URL-based connections
    - Color-coded database type icons
    - Collapsible advanced settings (SSH, SSL)
    - Keyboard shortcuts for power users
    """

    def __init__(
        self, manager: ConnectionManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect to Database")
        self.resize(800, 550)
        self.setObjectName("connection-dialog")

        self._manager = manager
        self._store = ConnectionStore()
        self._thread_pool = QThreadPool.globalInstance()

        self._active_driver: DatabaseDriver | None = None
        self._current_conn_id: str | None = None

        self._setup_ui()
        self._load_saved_connections()
        self._setup_shortcuts()

    @property
    def active_driver(self) -> DatabaseDriver | None:
        return self._active_driver

    # ── UI Setup ─────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Quick Connect Bar
        self._setup_quick_connect(layout)

        # ── Main Content (Split View)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # ── Left Panel: Saved Connections
        left_panel = self._setup_left_panel()
        content_layout.addWidget(left_panel)

        # ── Right Panel: Connection Form
        right_panel = self._setup_right_panel()
        content_layout.addWidget(right_panel, 1)

        layout.addLayout(content_layout)

    def _setup_quick_connect(self, parent_layout: QVBoxLayout) -> None:
        """Top bar for quick URL-based connections."""
        quick_bar = QWidget()
        quick_bar.setObjectName("quick-connect-bar")
        qb_layout = QHBoxLayout(quick_bar)
        qb_layout.setContentsMargins(16, 8, 16, 8)
        qb_layout.setSpacing(12)

        icon_label = QLabel("⚡")
        icon_label.setObjectName("quick-connect-icon")
        qb_layout.addWidget(icon_label)

        qb_layout.addWidget(QLabel("Quick Connect:"))

        self._url_input = QLineEdit()
        self._url_input.setObjectName("quick-connect-input")
        self._url_input.setPlaceholderText(
            "postgresql://user:pass@host:5432/db or mysql://user:pass@host:3306/db"
        )
        self._url_input.textChanged.connect(self._on_url_changed)
        qb_layout.addWidget(self._url_input, 1)

        self._quick_connect_btn = QPushButton("Connect")
        self._quick_connect_btn.setObjectName("quick-connect-btn")
        self._quick_connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quick_connect_btn.clicked.connect(self._on_quick_connect)
        qb_layout.addWidget(self._quick_connect_btn)

        parent_layout.addWidget(quick_bar)

        # Separator
        sep = QFrame()
        sep.setObjectName("connection-separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        parent_layout.addWidget(sep)

    def _setup_left_panel(self) -> QWidget:
        """Left panel with saved connections list."""
        left_panel = QWidget()
        left_panel.setObjectName("connection-list-panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Connections")
        title.setObjectName("connection-list-title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setObjectName("icon-btn-small")
        self._refresh_btn.setToolTip("Refresh list")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.clicked.connect(self._load_saved_connections)
        header_layout.addWidget(self._refresh_btn)

        left_layout.addWidget(header)

        # Connection list
        self._conn_list = QListWidget()
        self._conn_list.setObjectName("connection-list")
        self._conn_list.itemDoubleClicked.connect(self._on_connect_clicked)
        self._conn_list.itemSelectionChanged.connect(self._on_connection_selected)
        left_layout.addWidget(self._conn_list)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._new_btn = QPushButton("+ New")
        self._new_btn.setObjectName("connection-action-btn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self._on_new_clicked)
        btn_layout.addWidget(self._new_btn)

        self._delete_btn = QPushButton("🗑")
        self._delete_btn.setObjectName("connection-action-btn")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setToolTip("Delete selected")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self._delete_btn)

        left_layout.addLayout(btn_layout)

        left_panel.setFixedWidth(240)
        return left_panel

    def _setup_right_panel(self) -> QWidget:
        """Right panel with connection form."""
        right_panel = QWidget()
        right_panel.setObjectName("connection-form-panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 16, 20, 16)
        right_layout.setSpacing(12)

        # ── Form Header with Database Type Selector
        form_header = QWidget()
        fh_layout = QHBoxLayout(form_header)
        fh_layout.setContentsMargins(0, 0, 0, 0)

        self._driver_combo = QComboBox()
        self._driver_combo.setObjectName("driver-select")
        self._driver_combo.addItem("🐘 PostgreSQL", DriverType.POSTGRESQL.value)
        self._driver_combo.addItem("🐬 MySQL", DriverType.MYSQL.value)
        self._driver_combo.currentIndexChanged.connect(self._on_driver_changed)
        fh_layout.addWidget(self._driver_combo)

        fh_layout.addStretch()

        self._favorite_btn = QPushButton("★")
        self._favorite_btn.setObjectName("favorite-btn")
        self._favorite_btn.setToolTip("Toggle favorite")
        self._favorite_btn.setFixedSize(32, 32)
        fh_layout.addWidget(self._favorite_btn)

        right_layout.addWidget(form_header)

        # ── Connection Name
        self._name_input = QLineEdit()
        self._name_input.setObjectName("connection-name-input")
        self._name_input.setPlaceholderText("Connection name (e.g., Production DB)")
        right_layout.addWidget(self._name_input)

        # ── Main Form Fields
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(0, 0, 0, 0)

        # Host & Port in one row
        host_port_layout = QHBoxLayout()
        host_port_layout.setSpacing(8)

        self._host_input = QLineEdit()
        self._host_input.setObjectName("host-input")
        self._host_input.setPlaceholderText("localhost")
        host_port_layout.addWidget(self._host_input, 3)

        self._port_input = QSpinBox()
        self._port_input.setObjectName("port-input")
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(5432)
        self._port_input.setFixedWidth(80)
        host_port_layout.addWidget(self._port_input)

        host_widget = QWidget()
        host_widget.setLayout(host_port_layout)
        form_layout.addRow("Host:", host_widget)

        self._db_input = QLineEdit()
        self._db_input.setObjectName("database-input")
        self._db_input.setPlaceholderText("database_name")
        form_layout.addRow("Database:", self._db_input)

        self._user_input = QLineEdit()
        self._user_input.setObjectName("username-input")
        self._user_input.setPlaceholderText("username")
        form_layout.addRow("Username:", self._user_input)

        self._pass_input = QLineEdit()
        self._pass_input.setObjectName("password-input")
        self._pass_input.setPlaceholderText("password")
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self._pass_input)

        right_layout.addLayout(form_layout)

        # ── Advanced Settings (Collapsible)
        self._advanced_toggle = QPushButton("▼ Advanced Options")
        self._advanced_toggle.setObjectName("advanced-toggle")
        self._advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._advanced_toggle.clicked.connect(self._toggle_advanced)
        right_layout.addWidget(self._advanced_toggle)

        self._advanced_widget = QWidget()
        self._advanced_widget.setObjectName("advanced-panel")
        self._advanced_widget.setVisible(False)
        adv_layout = QFormLayout(self._advanced_widget)
        adv_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        adv_layout.setSpacing(8)
        adv_layout.setContentsMargins(0, 0, 0, 0)

        # SSL checkbox
        self._ssl_checkbox = QCheckBox("Use SSL/TLS")
        self._ssl_checkbox.setObjectName("ssl-checkbox")
        adv_layout.addRow("", self._ssl_checkbox)

        # SSL options (shown when checkbox is checked)
        self._ssl_verify_checkbox = QCheckBox("Verify server certificate")
        self._ssl_verify_checkbox.setObjectName("ssl-verify-checkbox")
        self._ssl_verify_checkbox.setChecked(True)
        adv_layout.addRow("", self._ssl_verify_checkbox)

        # SSH Tunnel section
        self._ssh_checkbox = QCheckBox("Use SSH Tunnel")
        self._ssh_checkbox.setObjectName("ssh-checkbox")
        adv_layout.addRow("", self._ssh_checkbox)

        self._ssh_host_input = QLineEdit()
        self._ssh_host_input.setObjectName("ssh-host-input")
        self._ssh_host_input.setPlaceholderText("SSH host")
        adv_layout.addRow("SSH Host:", self._ssh_host_input)

        self._ssh_port_input = QSpinBox()
        self._ssh_port_input.setObjectName("ssh-port-input")
        self._ssh_port_input.setRange(1, 65535)
        self._ssh_port_input.setValue(22)
        adv_layout.addRow("SSH Port:", self._ssh_port_input)

        self._ssh_user_input = QLineEdit()
        self._ssh_user_input.setObjectName("ssh-user-input")
        self._ssh_user_input.setPlaceholderText("SSH username")
        adv_layout.addRow("SSH User:", self._ssh_user_input)

        self._ssh_key_input = QLineEdit()
        self._ssh_key_input.setObjectName("ssh-key-input")
        self._ssh_key_input.setPlaceholderText("Path to private key file")
        adv_layout.addRow("SSH Key:", self._ssh_key_input)

        right_layout.addWidget(self._advanced_widget)

        right_layout.addStretch()

        # ── Action Buttons & Status
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("conn-status-label")
        actions_layout.addWidget(self._status_label)

        actions_layout.addStretch()

        self._test_btn = QPushButton("Test")
        self._test_btn.setObjectName("dialog-action-btn-secondary")
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setToolTip("Test connection (Ctrl+T)")
        self._test_btn.clicked.connect(self._on_test_clicked)
        actions_layout.addWidget(self._test_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("dialog-action-btn-secondary")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setToolTip("Save connection (Ctrl+S)")
        self._save_btn.clicked.connect(self._on_save_clicked)
        actions_layout.addWidget(self._save_btn)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("dialog-action-btn-primary")
        self._connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._connect_btn.setDefault(True)
        self._connect_btn.setToolTip("Connect to database (Ctrl+Enter)")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        actions_layout.addWidget(self._connect_btn)

        right_layout.addWidget(actions_widget)

        return right_panel

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts for power users."""
        from PySide6.QtGui import QShortcut, QKeySequence

        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_connect_clicked)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._on_connect_clicked)
        QShortcut(QKeySequence("Ctrl+T"), self, self._on_test_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save_clicked)
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_new_clicked)
        QShortcut(QKeySequence("Delete"), self._conn_list, self._on_delete_clicked)

    # ── State Management ─────────────────────────────────────

    def _load_saved_connections(self) -> None:
        self._conn_list.clear()
        profiles = self._store.load_all()

        # Group by favorite first
        favorites = [p for p in profiles if p.get("favorite", False)]
        others = [p for p in profiles if not p.get("favorite", False)]

        for p in favorites + others:
            self._add_connection_item(p)

    def _add_connection_item(self, profile: dict[str, Any]) -> None:
        dtype = profile.get("driver_type", "")
        driver_icon = self._get_driver_icon(dtype)
        name = profile.get("name", "Unnamed")

        # Add star for favorites
        if profile.get("favorite", False):
            name = "★ " + name

        item = QListWidgetItem(f"{driver_icon}  {name}")
        item.setData(Qt.ItemDataRole.UserRole, profile)

        # Set color based on database type
        color = QColor(self._get_driver_color(dtype))
        item.setForeground(color)

        self._conn_list.addItem(item)

    def _get_driver_icon(self, dtype: str) -> str:
        if dtype == DriverType.POSTGRESQL.value:
            return "🐘"
        elif dtype == DriverType.MYSQL.value:
            return "🐬"
        return "💾"

    def _get_driver_color(self, dtype: str) -> str:
        if dtype == DriverType.POSTGRESQL.value:
            return "#336791"
        elif dtype == DriverType.MYSQL.value:
            return "#F29111"
        return "#888888"

    def _get_form_profile(self) -> dict[str, Any]:
        return {
            "name": self._name_input.text().strip(),
            "driver_type": self._driver_combo.currentData(),
            "host": self._host_input.text().strip(),
            "port": self._port_input.value(),
            "database": self._db_input.text().strip(),
            "username": self._user_input.text().strip(),
            "password": self._pass_input.text(),
            "ssl": self._ssl_checkbox.isChecked(),
            "ssh_enabled": self._ssh_checkbox.isChecked(),
            "ssh_host": self._ssh_host_input.text().strip(),
            "ssh_port": self._ssh_port_input.value(),
            "ssh_user": self._ssh_user_input.text().strip(),
            "ssh_key": self._ssh_key_input.text().strip(),
        }

    def _set_form_profile(self, profile: dict[str, Any]) -> None:
        self._name_input.setText(profile.get("name", ""))

        dtype = profile.get("driver_type")
        idx = self._driver_combo.findData(dtype)
        if idx >= 0:
            self._driver_combo.setCurrentIndex(idx)

        self._host_input.setText(profile.get("host", "localhost"))
        self._port_input.setValue(int(profile.get("port", 5432)))
        self._db_input.setText(profile.get("database", ""))
        self._user_input.setText(profile.get("username", ""))
        self._pass_input.setText(profile.get("password", ""))

        # Advanced options
        self._ssl_checkbox.setChecked(profile.get("ssl", False))
        self._ssh_checkbox.setChecked(profile.get("ssh_enabled", False))
        self._ssh_host_input.setText(profile.get("ssh_host", ""))
        self._ssh_port_input.setValue(int(profile.get("ssh_port", 22)))
        self._ssh_user_input.setText(profile.get("ssh_user", ""))
        self._ssh_key_input.setText(profile.get("ssh_key", ""))

    def _set_ui_disabled(self, disabled: bool) -> None:
        self._test_btn.setDisabled(disabled)
        self._save_btn.setDisabled(disabled)
        self._connect_btn.setDisabled(disabled)
        self._conn_list.setDisabled(disabled)
        self._new_btn.setDisabled(disabled)
        self._delete_btn.setDisabled(disabled)
        self._quick_connect_btn.setDisabled(disabled)

        self._name_input.setDisabled(disabled)
        self._driver_combo.setDisabled(disabled)
        self._host_input.setDisabled(disabled)
        self._port_input.setDisabled(disabled)
        self._db_input.setDisabled(disabled)
        self._user_input.setDisabled(disabled)
        self._pass_input.setDisabled(disabled)
        self._url_input.setDisabled(disabled)

    # ── URL Parsing ───────────────────────────────────────────

    def _on_url_changed(self, url: str) -> None:
        """Parse connection URL and auto-fill form."""
        if not url:
            return

        parsed = self._parse_connection_url(url)
        if parsed:
            self._set_form_profile(parsed)

    def _parse_connection_url(self, url: str) -> dict[str, Any] | None:
        """Parse standard database connection URLs."""
        # postgres://user:pass@host:5432/db
        # mysql://user:pass@host:3306/db
        pattern = r"^(?P<driver>postgres|postgresql|mysql)://(?:(?P<user>[^:]+)(?::(?P<pass>[^@]+))?@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?(?:/(?P<db>.*))?$"
        match = re.match(pattern, url.strip(), re.IGNORECASE)
        if not match:
            return None

        data = match.groupdict()

        driver = data["driver"].lower()
        if driver in ("postgres", "postgresql"):
            dtype = DriverType.POSTGRESQL.value
            default_port = 5432
        else:
            dtype = DriverType.MYSQL.value
            default_port = 3306

        return {
            "driver_type": dtype,
            "host": data["host"] or "localhost",
            "port": int(data["port"]) if data["port"] else default_port,
            "database": data["db"] or "",
            "username": data["user"] or "",
            "password": data["pass"] or "",
        }

    # ── Slots ────────────────────────────────────────────────

    def _on_connection_selected(self) -> None:
        items = self._conn_list.selectedItems()
        if not items:
            return
        profile = items[0].data(Qt.ItemDataRole.UserRole)
        self._current_conn_id = profile.get("id")
        self._set_form_profile(profile)
        self._set_status("Ready", "normal")

    def _on_new_clicked(self) -> None:
        self._conn_list.clearSelection()
        self._current_conn_id = None
        self._set_form_profile({"driver_type": DriverType.POSTGRESQL.value})
        self._name_input.setFocus()
        self._set_status("New connection", "normal")

    def _on_delete_clicked(self) -> None:
        items = self._conn_list.selectedItems()
        if not items:
            return

        profile = items[0].data(Qt.ItemDataRole.UserRole)
        conn_id = profile.get("id")
        if conn_id:
            reply = QMessageBox.question(
                self,
                "Delete Connection",
                f"Delete '{profile.get('name')}'?\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._store.delete(conn_id)
                self._load_saved_connections()
                self._on_new_clicked()

    def _on_driver_changed(self) -> None:
        dtype = self._driver_combo.currentData()
        if dtype == DriverType.POSTGRESQL.value:
            if self._port_input.value() == 3306:
                self._port_input.setValue(5432)
        elif dtype == DriverType.MYSQL.value:
            if self._port_input.value() == 5432:
                self._port_input.setValue(3306)

    def _toggle_advanced(self) -> None:
        visible = not self._advanced_widget.isVisible()
        self._advanced_widget.setVisible(visible)
        self._advanced_toggle.setText(
            "▶ Advanced Options" if not visible else "▼ Advanced Options"
        )

    def _on_test_clicked(self) -> None:
        profile = self._get_form_profile()
        try:
            config = self._store.to_config(profile)
        except Exception as e:
            self._set_status(f"Validation Error: {e}", "error")
            return

        self._set_ui_disabled(True)
        self._set_status("Testing connection...", "loading")

        driver_cls = (
            PostgreSQLDriver
            if config.driver_type == DriverType.POSTGRESQL
            else MySQLDriver
        )
        self._test_driver = driver_cls(config)

        worker = QueryWorker(self._test_driver.test_connection)
        self._test_worker = worker

        worker.signals.finished.connect(
            lambda res, d=self._test_driver: self._on_test_finished(res, d)
        )
        worker.signals.error.connect(
            lambda err, d=self._test_driver: self._on_test_error(err, d)
        )
        self._thread_pool.start(worker)

    def _on_test_finished(self, success: bool, driver: DatabaseDriver) -> None:
        self._set_ui_disabled(False)
        if success:
            self._set_status("✓ Connection successful!", "success")
        else:
            self._set_status("✗ Connection failed", "error")
        self._test_driver = None
        self._test_worker = None

    def _on_test_error(self, error: Exception, driver: DatabaseDriver) -> None:
        self._set_ui_disabled(False)
        self._set_status(f"✗ {error}", "error")
        self._test_driver = None
        self._test_worker = None

    def _on_save_clicked(self) -> None:
        profile = self._get_form_profile()
        if not profile["name"]:
            self._name_input.setFocus()
            self._set_status("Enter a connection name", "error")
            return

        self._current_conn_id = self._store.save(profile, self._current_conn_id)
        self._load_saved_connections()

        # Select the newly saved item
        for i in range(self._conn_list.count()):
            item = self._conn_list.item(i)
            p = item.data(Qt.ItemDataRole.UserRole)
            if p.get("id") == self._current_conn_id:
                self._conn_list.setCurrentItem(item)
                break

        self._set_status("✓ Saved", "success")

    def _on_connect_clicked(self) -> None:
        profile = self._get_form_profile()
        if not profile["name"]:
            self._name_input.setFocus()
            self._set_status("Enter a connection name", "error")
            return

        self._current_conn_id = self._store.save(profile, self._current_conn_id)
        try:
            config = self._store.to_config(profile)
        except Exception as e:
            self._set_status(f"Error: {e}", "error")
            return

        self._set_ui_disabled(True)
        self._set_status("Connecting...", "loading")

        if self._current_conn_id in self._manager.active_connections:
            self._manager.close_connection(self._current_conn_id)

        worker = QueryWorker(
            self._manager.create_connection, self._current_conn_id, config
        )
        worker.signals.finished.connect(self._on_connect_finished)
        worker.signals.error.connect(self._on_connect_error)
        self._thread_pool.start(worker)

    def _on_connect_finished(self, driver: DatabaseDriver) -> None:
        self._set_ui_disabled(False)
        self._active_driver = driver
        self.accept()

    def _on_connect_error(self, error: Exception) -> None:
        self._set_ui_disabled(False)
        self._set_status(f"✗ {error}", "error")

        if (
            self._current_conn_id
            and self._current_conn_id in self._manager.active_connections
        ):
            self._manager.close_connection(self._current_conn_id)

    def _on_quick_connect(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return

        profile = self._parse_connection_url(url)
        if not profile:
            self._set_status("Invalid URL format", "error")
            return

        # Auto-generate name from URL
        profile["name"] = f"Quick Connect ({profile['host']})"

        try:
            config = self._store.to_config(profile)
        except Exception as e:
            self._set_status(f"Error: {e}", "error")
            return

        self._set_ui_disabled(True)
        self._set_status("Connecting...", "loading")

        worker = QueryWorker(self._manager.create_connection, None, config)
        worker.signals.finished.connect(self._on_connect_finished)
        worker.signals.error.connect(self._on_connect_error)
        self._thread_pool.start(worker)

    def _set_status(self, message: str, status_type: str) -> None:
        """Set status label with appropriate styling."""
        self._status_label.setText(message)

        if status_type == "error":
            self._status_label.setStyleSheet("color: #ef4444;")
        elif status_type == "success":
            self._status_label.setStyleSheet("color: #22c55e;")
        elif status_type == "loading":
            self._status_label.setStyleSheet("color: #3b82f6;")
        else:
            self._status_label.setStyleSheet("color: #6b7280;")
