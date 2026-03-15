"""Connection dialog - clean single-panel design with driver card selection."""

import re
from typing import Any

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
from tablefree.theme import current
from tablefree.workers import QueryWorker


class ConnectionDialog(QDialog):
    """Modal dialog for creating and managing database connections.

    Features:
    - Clickable driver cards for database type selection
    - Grid-based form layout
    - Password visibility toggle
    - Collapsible advanced settings (SSH, SSL)
    - Saved connections dropdown
    - Keyboard shortcuts for power users
    """

    def __init__(
        self, manager: ConnectionManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Connection")
        self.resize(600, 500)
        self.setObjectName("connection-dialog")

        self._manager = manager
        self._store = ConnectionStore()
        self._thread_pool = QThreadPool.globalInstance()

        self._active_driver: DatabaseDriver | None = None
        self._current_conn_id: str | None = None
        self._selected_driver: str = DriverType.POSTGRESQL.value
        self._driver_cards: dict[str, QPushButton] = {}

        self._setup_ui()
        self._load_saved_connections()
        self._setup_shortcuts()

    @property
    def active_driver(self) -> DatabaseDriver | None:
        return self._active_driver

    # -- UI Setup ----------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # -- Title row with saved connections dropdown
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_label = QLabel("New Connection")
        title_label.setObjectName("connection-dialog-title")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Saved connections dropdown
        self._saved_combo = QComboBox()
        self._saved_combo.setObjectName("saved-connections-combo")
        self._saved_combo.setMinimumWidth(180)
        self._saved_combo.setPlaceholderText("Saved connections...")
        self._saved_combo.currentIndexChanged.connect(self._on_connection_selected)
        header_layout.addWidget(self._saved_combo)

        self._new_btn = QPushButton("New")
        self._new_btn.setObjectName("connection-new-btn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setToolTip("Clear form for new connection (Ctrl+N)")
        self._new_btn.clicked.connect(self._on_new_clicked)
        header_layout.addWidget(self._new_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("connection-delete-btn")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setToolTip("Delete selected connection")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        header_layout.addWidget(self._delete_btn)

        layout.addLayout(header_layout)

        # -- Driver cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        for driver_value, label_text in [
            (DriverType.POSTGRESQL.value, "PostgreSQL"),
            (DriverType.MYSQL.value, "MySQL"),
        ]:
            card = QPushButton(label_text)
            card.setObjectName("driver-card")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setCheckable(True)
            card.setMinimumHeight(60)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.clicked.connect(
                lambda checked, dv=driver_value: self._on_driver_card_clicked(dv)
            )
            cards_layout.addWidget(card)
            self._driver_cards[driver_value] = card

        # Select PostgreSQL by default
        self._select_driver_card(DriverType.POSTGRESQL.value)

        layout.addLayout(cards_layout)

        # -- Form fields in grid layout
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 1)

        # Row 0-1: Connection Name + Port
        name_label = QLabel("Connection Name")
        name_label.setObjectName("form-label")
        grid.addWidget(name_label, 0, 0)

        port_label = QLabel("Port")
        port_label.setObjectName("form-label")
        grid.addWidget(port_label, 0, 1)

        self._name_input = QLineEdit()
        self._name_input.setObjectName("connection-name-input")
        self._name_input.setPlaceholderText("e.g., Production DB")
        grid.addWidget(self._name_input, 1, 0)

        self._port_input = QSpinBox()
        self._port_input.setObjectName("port-input")
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(5432)
        grid.addWidget(self._port_input, 1, 1)

        # Row 2-3: Host + Password
        host_label = QLabel("Host")
        host_label.setObjectName("form-label")
        grid.addWidget(host_label, 2, 0)

        password_label = QLabel("Password")
        password_label.setObjectName("form-label")
        grid.addWidget(password_label, 2, 1)

        self._host_input = QLineEdit()
        self._host_input.setObjectName("host-input")
        self._host_input.setPlaceholderText("localhost")
        grid.addWidget(self._host_input, 3, 0)

        # Password field with visibility toggle
        pass_widget = QWidget()
        pass_widget.setObjectName("password-widget")
        pass_layout = QHBoxLayout(pass_widget)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(4)

        self._pass_input = QLineEdit()
        self._pass_input.setObjectName("password-input")
        self._pass_input.setPlaceholderText("password")
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        pass_layout.addWidget(self._pass_input)

        self._pass_toggle_btn = QPushButton("Show")
        self._pass_toggle_btn.setObjectName("password-toggle-btn")
        self._pass_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pass_toggle_btn.setFixedWidth(48)
        self._pass_toggle_btn.setToolTip("Toggle password visibility")
        self._pass_toggle_btn.clicked.connect(self._toggle_password_visibility)
        pass_layout.addWidget(self._pass_toggle_btn)

        grid.addWidget(pass_widget, 3, 1)

        # Row 4-5: User (full width)
        user_label = QLabel("User")
        user_label.setObjectName("form-label")
        grid.addWidget(user_label, 4, 0, 1, 2)

        self._user_input = QLineEdit()
        self._user_input.setObjectName("username-input")
        self._user_input.setPlaceholderText("username")
        grid.addWidget(self._user_input, 5, 0, 1, 2)

        # Row 6-7: Database Name (full width)
        db_label = QLabel("Database Name")
        db_label.setObjectName("form-label")
        grid.addWidget(db_label, 6, 0, 1, 2)

        self._db_input = QLineEdit()
        self._db_input.setObjectName("database-input")
        self._db_input.setPlaceholderText("database_name")
        grid.addWidget(self._db_input, 7, 0, 1, 2)

        layout.addLayout(grid)

        # -- Advanced Options (Collapsible)
        self._advanced_toggle = QPushButton("Advanced Options")
        self._advanced_toggle.setObjectName("advanced-toggle")
        self._advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._advanced_toggle.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._advanced_toggle)

        self._advanced_widget = QWidget()
        self._advanced_widget.setObjectName("advanced-panel")
        self._advanced_widget.setVisible(False)
        adv_layout = QFormLayout(self._advanced_widget)
        adv_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        adv_layout.setSpacing(8)
        adv_layout.setContentsMargins(0, 0, 0, 0)

        self._ssl_checkbox = QCheckBox("Use SSL/TLS")
        self._ssl_checkbox.setObjectName("ssl-checkbox")
        adv_layout.addRow("", self._ssl_checkbox)

        self._ssl_verify_checkbox = QCheckBox("Verify server certificate")
        self._ssl_verify_checkbox.setObjectName("ssl-verify-checkbox")
        self._ssl_verify_checkbox.setChecked(True)
        adv_layout.addRow("", self._ssl_verify_checkbox)

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

        layout.addWidget(self._advanced_widget)

        layout.addStretch()

        # -- Status and action buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("conn-status-label")
        bottom_layout.addWidget(self._status_label)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("dialog-action-btn-cancel")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self._cancel_btn)

        bottom_layout.addStretch()

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setObjectName("dialog-action-btn-secondary")
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setToolTip("Test connection (Ctrl+T)")
        self._test_btn.clicked.connect(self._on_test_clicked)
        bottom_layout.addWidget(self._test_btn)

        self._connect_btn = QPushButton("Save && Connect")
        self._connect_btn.setObjectName("dialog-action-btn-primary")
        self._connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._connect_btn.setDefault(True)
        self._connect_btn.setToolTip("Save and connect (Ctrl+Enter)")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        bottom_layout.addWidget(self._connect_btn)

        layout.addLayout(bottom_layout)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts for power users."""
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_connect_clicked)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._on_connect_clicked)
        QShortcut(QKeySequence("Ctrl+T"), self, self._on_test_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save_clicked)
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_new_clicked)

    # -- Driver Card Selection ---------------------------------------------

    def _select_driver_card(self, driver_value: str) -> None:
        """Update visual selection state of driver cards."""
        self._selected_driver = driver_value
        for dv, card in self._driver_cards.items():
            if dv == driver_value:
                card.setChecked(True)
                card.setObjectName("driver-card-selected")
            else:
                card.setChecked(False)
                card.setObjectName("driver-card")
            # Force style refresh
            card.style().unpolish(card)
            card.style().polish(card)

    def _on_driver_card_clicked(self, driver_value: str) -> None:
        """Handle driver card click."""
        self._select_driver_card(driver_value)
        self._on_driver_changed()

    def _toggle_password_visibility(self) -> None:
        """Toggle password field between visible and hidden."""
        if self._pass_input.echoMode() == QLineEdit.EchoMode.Password:
            self._pass_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._pass_toggle_btn.setText("Hide")
        else:
            self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._pass_toggle_btn.setText("Show")

    # -- State Management --------------------------------------------------

    def _load_saved_connections(self) -> None:
        self._saved_combo.blockSignals(True)
        self._saved_combo.clear()
        self._saved_combo.addItem("-- New Connection --", None)

        profiles = self._store.load_all()
        for p in profiles:
            name = p.get("name", "Unnamed")
            dtype = p.get("driver_type", "")
            prefix = self._get_driver_prefix(dtype)
            self._saved_combo.addItem(f"{prefix}{name}", p)

        self._saved_combo.blockSignals(False)

    def _get_driver_prefix(self, dtype: str) -> str:
        if dtype == DriverType.POSTGRESQL.value:
            return "[PG] "
        elif dtype == DriverType.MYSQL.value:
            return "[MY] "
        return ""

    def _get_form_profile(self) -> dict[str, Any]:
        return {
            "name": self._name_input.text().strip(),
            "driver_type": self._selected_driver,
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

        dtype = profile.get("driver_type", DriverType.POSTGRESQL.value)
        self._select_driver_card(dtype)

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
        self._connect_btn.setDisabled(disabled)
        self._cancel_btn.setDisabled(disabled)
        self._saved_combo.setDisabled(disabled)
        self._new_btn.setDisabled(disabled)
        self._delete_btn.setDisabled(disabled)

        self._name_input.setDisabled(disabled)
        self._host_input.setDisabled(disabled)
        self._port_input.setDisabled(disabled)
        self._db_input.setDisabled(disabled)
        self._user_input.setDisabled(disabled)
        self._pass_input.setDisabled(disabled)

        for card in self._driver_cards.values():
            card.setDisabled(disabled)

    # -- URL Parsing -------------------------------------------------------

    def _parse_connection_url(self, url: str) -> dict[str, Any] | None:
        """Parse standard database connection URLs."""
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

    # -- Slots -------------------------------------------------------------

    def _on_connection_selected(self) -> None:
        idx = self._saved_combo.currentIndex()
        if idx <= 0:
            # "-- New Connection --" or nothing selected
            return
        profile = self._saved_combo.currentData()
        if profile is None:
            return
        self._current_conn_id = profile.get("id")
        self._set_form_profile(profile)
        self._set_status("Ready", "normal")

    def _on_new_clicked(self) -> None:
        self._saved_combo.blockSignals(True)
        self._saved_combo.setCurrentIndex(0)
        self._saved_combo.blockSignals(False)
        self._current_conn_id = None
        self._set_form_profile({"driver_type": DriverType.POSTGRESQL.value})
        self._name_input.setFocus()
        self._set_status("New connection", "normal")

    def _on_delete_clicked(self) -> None:
        idx = self._saved_combo.currentIndex()
        if idx <= 0:
            return

        profile = self._saved_combo.currentData()
        if profile is None:
            return

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
        dtype = self._selected_driver
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
            "Advanced Options" if not visible else "Advanced Options"
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

        worker.signals.finished.connect(self._on_test_finished)
        worker.signals.error.connect(self._on_test_error)
        self._thread_pool.start(worker)

    def _on_test_finished(self, success: bool) -> None:
        self._set_ui_disabled(False)
        if success:
            self._set_status("Connection successful!", "success")
        else:
            self._set_status("Connection failed", "error")
        self._test_driver = None
        self._test_worker = None

    def _on_test_error(self, error: Exception) -> None:
        self._set_ui_disabled(False)
        self._set_status(f"Error: {error}", "error")
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

        # Select the newly saved item in the combo
        for i in range(self._saved_combo.count()):
            p = self._saved_combo.itemData(i)
            if p and isinstance(p, dict) and p.get("id") == self._current_conn_id:
                self._saved_combo.blockSignals(True)
                self._saved_combo.setCurrentIndex(i)
                self._saved_combo.blockSignals(False)
                break

        self._set_status("Saved", "success")

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
        self._set_status(f"Error: {error}", "error")

        if (
            self._current_conn_id
            and self._current_conn_id in self._manager.active_connections
        ):
            self._manager.close_connection(self._current_conn_id)

    def _set_status(self, message: str, status_type: str) -> None:
        """Set status label with appropriate styling."""
        colors = current()
        self._status_label.setText(message)

        if status_type == "error":
            self._status_label.setStyleSheet(f"color: {colors.error.name()};")
        elif status_type == "success":
            self._status_label.setStyleSheet(f"color: {colors.success.name()};")
        elif status_type == "loading":
            self._status_label.setStyleSheet(f"color: {colors.info.name()};")
        else:
            self._status_label.setStyleSheet(f"color: {colors.muted.name()};")
