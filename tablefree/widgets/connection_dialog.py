"""Connection dialog with two-panel connection manager UX."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tablefree.db.config import DriverType
from tablefree.db.connection_store import ConnectionStore
from tablefree.db.driver import DatabaseDriver
from tablefree.db.manager import ConnectionManager
from tablefree.db.mysql_driver import MySQLDriver
from tablefree.db.postgres_driver import PostgreSQLDriver
from tablefree.theme import current
from tablefree.workers import QueryWorker

_ROOT = Path(__file__).resolve().parents[2]
_RESOURCES = _ROOT / "resources"


class ConnectionDialog(QDialog):
    """Modal dialog for managing and connecting database profiles."""

    def __init__(
        self, manager: ConnectionManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connection Manager")
        self.resize(860, 560)
        self.setObjectName("connection-dialog")

        self._manager = manager
        self._store = ConnectionStore()
        self._thread_pool = QThreadPool.globalInstance()

        self._active_driver: DatabaseDriver | None = None
        self._current_conn_id: str | None = None
        self._selected_driver: str = DriverType.POSTGRESQL.value
        self._driver_cards: dict[str, QPushButton] = {}
        self._profiles_by_id: dict[str, dict[str, Any]] = {}

        self._setup_ui()
        self._load_saved_connections()
        self._on_new_clicked()
        self._setup_shortcuts()

    @property
    def active_driver(self) -> DatabaseDriver | None:
        return self._active_driver

    # -- UI Setup ----------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        split_layout = QHBoxLayout()
        split_layout.setSpacing(14)
        root.addLayout(split_layout, stretch=1)

        # -- Left panel: saved connection list
        left_panel = QWidget()
        left_panel.setObjectName("connection-list-panel")
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        left_title = QLabel("Saved Connections")
        left_title.setObjectName("connection-list-title")
        left_layout.addWidget(left_title)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("connection-search")
        self._search_input.setPlaceholderText("Search connections...")
        self._search_input.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self._search_input)

        self._connection_list = QListWidget()
        self._connection_list.setObjectName("connection-list")
        self._connection_list.setSpacing(2)
        self._connection_list.itemSelectionChanged.connect(
            self._on_connection_list_selected
        )
        self._connection_list.itemDoubleClicked.connect(
            self._on_connection_list_double_clicked
        )
        self._connection_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._connection_list.customContextMenuRequested.connect(
            self._on_connection_list_context_menu
        )
        left_layout.addWidget(self._connection_list, stretch=1)

        self._new_btn = QPushButton("+ New Connection")
        self._new_btn.setObjectName("connection-new-btn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self._on_new_clicked)
        left_layout.addWidget(self._new_btn)

        split_layout.addWidget(left_panel)

        # -- Right panel: form
        right_panel = QWidget()
        right_panel.setObjectName("connection-form-panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(12)
        split_layout.addWidget(right_panel, stretch=1)

        header_layout = QHBoxLayout()
        self._title_label = QLabel("New Connection")
        self._title_label.setObjectName("connection-dialog-title")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        right_layout.addLayout(header_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        for driver_value, label_text in (
            (DriverType.POSTGRESQL.value, "PostgreSQL"),
            (DriverType.MYSQL.value, "MySQL"),
        ):
            card = QPushButton(label_text)
            card.setObjectName("driver-card")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setCheckable(True)
            card.setMinimumHeight(52)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.clicked.connect(
                lambda checked, dv=driver_value: self._on_driver_card_clicked(dv)
            )
            cards_layout.addWidget(card)
            self._driver_cards[driver_value] = card
        self._select_driver_card(DriverType.POSTGRESQL.value)
        right_layout.addLayout(cards_layout)

        # -- Main form layout
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        name_label = QLabel("Connection Name")
        name_label.setObjectName("form-label")
        form_layout.addWidget(name_label)
        self._name_input = QLineEdit()
        self._name_input.setObjectName("connection-name-input")
        self._name_input.setPlaceholderText("e.g., Production DB")
        form_layout.addWidget(self._name_input)

        host_port_labels = QHBoxLayout()
        host_label = QLabel("Host")
        host_label.setObjectName("form-label")
        port_label = QLabel("Port")
        port_label.setObjectName("form-label")
        host_port_labels.addWidget(host_label, stretch=3)
        host_port_labels.addWidget(port_label, stretch=1)
        form_layout.addLayout(host_port_labels)

        host_port_row = QHBoxLayout()
        self._host_input = QLineEdit()
        self._host_input.setObjectName("host-input")
        self._host_input.setPlaceholderText("localhost")
        host_port_row.addWidget(self._host_input, stretch=3)
        self._port_input = QSpinBox()
        self._port_input.setObjectName("port-input")
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(5432)
        host_port_row.addWidget(self._port_input, stretch=1)
        form_layout.addLayout(host_port_row)

        user_label = QLabel("Username")
        user_label.setObjectName("form-label")
        form_layout.addWidget(user_label)
        self._user_input = QLineEdit()
        self._user_input.setObjectName("username-input")
        self._user_input.setPlaceholderText("username")
        form_layout.addWidget(self._user_input)

        pass_label = QLabel("Password")
        pass_label.setObjectName("form-label")
        form_layout.addWidget(pass_label)
        pass_widget = QWidget()
        pass_layout = QHBoxLayout(pass_widget)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(6)
        self._pass_input = QLineEdit()
        self._pass_input.setObjectName("password-input")
        self._pass_input.setPlaceholderText("password")
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        pass_layout.addWidget(self._pass_input)
        self._pass_toggle_btn = QPushButton("Show")
        self._pass_toggle_btn.setObjectName("password-toggle-btn")
        self._pass_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pass_toggle_btn.clicked.connect(self._toggle_password_visibility)
        pass_layout.addWidget(self._pass_toggle_btn)
        form_layout.addWidget(pass_widget)

        db_label = QLabel("Database Name")
        db_label.setObjectName("form-label")
        form_layout.addWidget(db_label)
        self._db_input = QLineEdit()
        self._db_input.setObjectName("database-input")
        self._db_input.setPlaceholderText("database_name")
        form_layout.addWidget(self._db_input)

        right_layout.addLayout(form_layout)

        self._advanced_toggle = QPushButton("Advanced Options")
        self._advanced_toggle.setObjectName("advanced-toggle")
        self._advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._advanced_toggle.clicked.connect(self._toggle_advanced)
        right_layout.addWidget(self._advanced_toggle)

        self._advanced_widget = QWidget()
        self._advanced_widget.setObjectName("advanced-panel")
        self._advanced_widget.setVisible(False)
        adv_layout = QVBoxLayout(self._advanced_widget)
        adv_layout.setSpacing(8)
        adv_layout.setContentsMargins(0, 0, 0, 0)

        ssl_title = QLabel("SSL / TLS")
        ssl_title.setObjectName("advanced-section-title")
        adv_layout.addWidget(ssl_title)

        self._ssl_checkbox = QCheckBox("Use SSL/TLS")
        self._ssl_checkbox.setObjectName("ssl-checkbox")
        self._ssl_checkbox.toggled.connect(self._on_ssl_toggled)
        adv_layout.addWidget(self._ssl_checkbox)

        self._ssl_verify_checkbox = QCheckBox("Verify server certificate")
        self._ssl_verify_checkbox.setObjectName("ssl-verify-checkbox")
        self._ssl_verify_checkbox.setChecked(True)
        ssl_verify_row = QWidget()
        ssl_verify_layout = QHBoxLayout(ssl_verify_row)
        ssl_verify_layout.setContentsMargins(22, 0, 0, 0)
        ssl_verify_layout.addWidget(self._ssl_verify_checkbox)
        ssl_verify_layout.addStretch()
        adv_layout.addWidget(ssl_verify_row)

        separator = QFrame()
        separator.setObjectName("advanced-separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        adv_layout.addWidget(separator)

        ssh_title = QLabel("SSH Tunnel")
        ssh_title.setObjectName("advanced-section-title")
        adv_layout.addWidget(ssh_title)

        self._ssh_checkbox = QCheckBox("Use SSH Tunnel")
        self._ssh_checkbox.setObjectName("ssh-checkbox")
        self._ssh_checkbox.toggled.connect(self._on_ssh_toggled)
        adv_layout.addWidget(self._ssh_checkbox)

        self._ssh_fields_container = QWidget()
        self._ssh_fields_container.setObjectName("ssh-fields-container")
        ssh_fields_layout = QVBoxLayout(self._ssh_fields_container)
        ssh_fields_layout.setContentsMargins(16, 4, 0, 0)
        ssh_fields_layout.setSpacing(8)

        ssh_host_port_labels = QHBoxLayout()
        ssh_host_label = QLabel("SSH Host")
        ssh_host_label.setObjectName("form-label")
        ssh_port_label = QLabel("SSH Port")
        ssh_port_label.setObjectName("form-label")
        ssh_host_port_labels.addWidget(ssh_host_label, stretch=3)
        ssh_host_port_labels.addWidget(ssh_port_label, stretch=1)
        ssh_fields_layout.addLayout(ssh_host_port_labels)

        ssh_host_port_row = QHBoxLayout()
        self._ssh_host_input = QLineEdit()
        self._ssh_host_input.setObjectName("ssh-host-input")
        self._ssh_host_input.setPlaceholderText("SSH host")
        ssh_host_port_row.addWidget(self._ssh_host_input, stretch=3)

        self._ssh_port_input = QSpinBox()
        self._ssh_port_input.setObjectName("ssh-port-input")
        self._ssh_port_input.setRange(1, 65535)
        self._ssh_port_input.setValue(22)
        ssh_host_port_row.addWidget(self._ssh_port_input, stretch=1)
        ssh_fields_layout.addLayout(ssh_host_port_row)

        ssh_user_label = QLabel("SSH User")
        ssh_user_label.setObjectName("form-label")
        ssh_fields_layout.addWidget(ssh_user_label)

        self._ssh_user_input = QLineEdit()
        self._ssh_user_input.setObjectName("ssh-user-input")
        self._ssh_user_input.setPlaceholderText("SSH username")
        ssh_fields_layout.addWidget(self._ssh_user_input)

        ssh_key_label = QLabel("SSH Key")
        ssh_key_label.setObjectName("form-label")
        ssh_fields_layout.addWidget(ssh_key_label)

        ssh_key_row = QHBoxLayout()
        self._ssh_key_input = QLineEdit()
        self._ssh_key_input.setObjectName("ssh-key-input")
        self._ssh_key_input.setPlaceholderText("Path to private key file")
        ssh_key_row.addWidget(self._ssh_key_input, stretch=1)
        self._ssh_key_browse_btn = QPushButton("Browse...")
        self._ssh_key_browse_btn.setObjectName("ssh-key-browse-btn")
        self._ssh_key_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ssh_key_browse_btn.clicked.connect(self._on_browse_ssh_key)
        ssh_key_row.addWidget(self._ssh_key_browse_btn)
        ssh_fields_layout.addLayout(ssh_key_row)

        adv_layout.addWidget(self._ssh_fields_container)
        right_layout.addWidget(self._advanced_widget)

        right_layout.addStretch()
        self._on_ssl_toggled(self._ssl_checkbox.isChecked())
        self._on_ssh_toggled(self._ssh_checkbox.isChecked())

        # -- Bottom action bar
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("conn-status-label")
        bottom_layout.addWidget(self._status_label)
        bottom_layout.addStretch()

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("dialog-action-btn-cancel")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        bottom_layout.addWidget(self._delete_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("dialog-action-btn-cancel")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self._cancel_btn)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setObjectName("dialog-action-btn-secondary")
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.clicked.connect(self._on_test_clicked)
        bottom_layout.addWidget(self._test_btn)

        self._connect_btn = QPushButton("Save && Connect")
        self._connect_btn.setObjectName("dialog-action-btn-primary")
        self._connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._connect_btn.setDefault(True)
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        bottom_layout.addWidget(self._connect_btn)

        right_layout.addLayout(bottom_layout)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_connect_clicked)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._on_connect_clicked)
        QShortcut(QKeySequence("Ctrl+T"), self, self._on_test_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save_clicked)
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_new_clicked)

    # -- Driver Card Selection ---------------------------------------------

    def _select_driver_card(self, driver_value: str) -> None:
        self._selected_driver = driver_value
        for dv, card in self._driver_cards.items():
            if dv == driver_value:
                card.setChecked(True)
                card.setObjectName("driver-card-selected")
            else:
                card.setChecked(False)
                card.setObjectName("driver-card")
            card.style().unpolish(card)
            card.style().polish(card)

    def _on_driver_card_clicked(self, driver_value: str) -> None:
        self._select_driver_card(driver_value)
        self._on_driver_changed()

    def _toggle_password_visibility(self) -> None:
        if self._pass_input.echoMode() == QLineEdit.EchoMode.Password:
            self._pass_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._pass_toggle_btn.setText("Hide")
        else:
            self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._pass_toggle_btn.setText("Show")

    # -- State Management --------------------------------------------------

    def _load_saved_connections(self) -> None:
        self._profiles_by_id = {}
        profiles = self._store.load_all()
        for profile in profiles:
            profile_id = profile.get("id")
            if profile_id:
                self._profiles_by_id[profile_id] = profile
        self._refresh_connection_list()

    def _refresh_connection_list(self) -> None:
        current_id = self._current_conn_id
        query = self._search_input.text().strip().lower()
        self._connection_list.blockSignals(True)
        self._connection_list.clear()

        for profile in self._store.load_all():
            profile_id = profile.get("id")
            if not profile_id:
                continue
            name = profile.get("name", "Unnamed")
            host = profile.get("host", "localhost")
            port = profile.get("port", "")
            driver = profile.get("driver_type", "")
            search_blob = f"{name} {host} {port} {driver}".lower()
            if query and query not in search_blob:
                continue

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, profile_id)
            item.setToolTip(f"{name}\n{driver.upper()}  {host}:{port}")
            item_widget = self._create_connection_item_widget(profile)
            item.setSizeHint(item_widget.sizeHint().expandedTo(item_widget.minimumSizeHint()))
            self._connection_list.addItem(item)
            self._connection_list.setItemWidget(item, item_widget)

            if profile_id == current_id:
                self._connection_list.setCurrentItem(item)

        self._connection_list.blockSignals(False)
        self._update_connection_item_selection_styles()
        self._update_title()

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

    def _create_connection_item_widget(self, profile: dict[str, Any]) -> QWidget:
        item_widget = QWidget()
        item_widget.setObjectName("connection-item-widget")
        item_widget.setMinimumHeight(52)
        row_layout = QHBoxLayout(item_widget)
        row_layout.setContentsMargins(6, 8, 6, 8)
        row_layout.setSpacing(10)

        driver = str(profile.get("driver_type", DriverType.POSTGRESQL.value))
        icon_name = (
            "postgresql.svg" if driver == DriverType.POSTGRESQL.value else "mysql.svg"
        )
        icon_label = QLabel()
        icon_label.setObjectName("driver-icon")
        icon_label.setFixedSize(18, 18)
        icon_path = _RESOURCES / "icons" / icon_name
        icon_pixmap = QIcon(str(icon_path)).pixmap(18, 18) if icon_path.exists() else None

        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("PG" if driver == DriverType.POSTGRESQL.value else "MY")
            icon_label.setObjectName(
                "driver-badge-pg"
                if driver == DriverType.POSTGRESQL.value
                else "driver-badge-my"
            )
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedWidth(30)

        row_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(3)

        name = str(profile.get("name", "Unnamed"))
        name_label = QLabel(name)
        name_label.setObjectName("conn-item-name")
        content_layout.addWidget(name_label)

        host = str(profile.get("host", "localhost"))
        port = str(profile.get("port", ""))
        database = str(profile.get("database", "")).strip()
        detail_text = f"{host}:{port}" if not database else f"{host}:{port} / {database}"
        detail_label = QLabel(detail_text)
        detail_label.setObjectName("conn-item-detail")
        content_layout.addWidget(detail_label)

        row_layout.addLayout(content_layout, stretch=1)
        return item_widget

    def _update_connection_item_selection_styles(self) -> None:
        current_item = self._connection_list.currentItem()
        for index in range(self._connection_list.count()):
            item = self._connection_list.item(index)
            widget = self._connection_list.itemWidget(item)
            if widget is None:
                continue
            widget.setProperty("selected", item == current_item)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _set_form_profile(self, profile: dict[str, Any]) -> None:
        self._name_input.setText(profile.get("name", ""))
        self._select_driver_card(profile.get("driver_type", DriverType.POSTGRESQL.value))
        self._host_input.setText(profile.get("host", "localhost"))
        self._port_input.setValue(int(profile.get("port", 5432)))
        self._db_input.setText(profile.get("database", ""))
        self._user_input.setText(profile.get("username", ""))
        self._pass_input.setText(profile.get("password", ""))
        self._ssl_checkbox.setChecked(profile.get("ssl", False))
        self._ssh_checkbox.setChecked(profile.get("ssh_enabled", False))
        self._ssh_host_input.setText(profile.get("ssh_host", ""))
        self._ssh_port_input.setValue(int(profile.get("ssh_port", 22)))
        self._ssh_user_input.setText(profile.get("ssh_user", ""))
        self._ssh_key_input.setText(profile.get("ssh_key", ""))
        self._on_ssl_toggled(self._ssl_checkbox.isChecked())
        self._on_ssh_toggled(self._ssh_checkbox.isChecked())
        self._update_title()
        self._delete_btn.setEnabled(self._current_conn_id is not None)

    def _set_ui_disabled(self, disabled: bool) -> None:
        self._test_btn.setDisabled(disabled)
        self._connect_btn.setDisabled(disabled)
        self._cancel_btn.setDisabled(disabled)
        self._delete_btn.setDisabled(disabled or self._current_conn_id is None)
        self._new_btn.setDisabled(disabled)
        self._search_input.setDisabled(disabled)
        self._connection_list.setDisabled(disabled)

        self._name_input.setDisabled(disabled)
        self._host_input.setDisabled(disabled)
        self._port_input.setDisabled(disabled)
        self._db_input.setDisabled(disabled)
        self._user_input.setDisabled(disabled)
        self._pass_input.setDisabled(disabled)
        self._advanced_toggle.setDisabled(disabled)
        self._ssl_checkbox.setDisabled(disabled)
        self._ssl_verify_checkbox.setDisabled(disabled)
        self._ssh_checkbox.setDisabled(disabled)
        self._ssh_host_input.setDisabled(disabled)
        self._ssh_port_input.setDisabled(disabled)
        self._ssh_user_input.setDisabled(disabled)
        self._ssh_key_input.setDisabled(disabled)
        self._ssh_key_browse_btn.setDisabled(disabled or not self._ssh_checkbox.isChecked())

        for card in self._driver_cards.values():
            card.setDisabled(disabled)

    def _update_title(self) -> None:
        if self._current_conn_id and self._name_input.text().strip():
            self._title_label.setText(f"Edit: {self._name_input.text().strip()}")
        else:
            self._title_label.setText("New Connection")

    # -- Slots -------------------------------------------------------------

    def _on_search_changed(self, _: str) -> None:
        self._refresh_connection_list()

    def _on_connection_list_selected(self) -> None:
        item = self._connection_list.currentItem()
        if not item:
            return
        conn_id = item.data(Qt.ItemDataRole.UserRole)
        if not conn_id:
            return
        profile = self._store.load(conn_id)
        if profile is None:
            return
        self._current_conn_id = conn_id
        self._set_form_profile(profile)
        self._update_connection_item_selection_styles()
        self._set_status("Ready", "normal")

    def _on_connection_list_double_clicked(self, item: QListWidgetItem) -> None:
        conn_id = item.data(Qt.ItemDataRole.UserRole)
        if not conn_id:
            return
        profile = self._store.load(conn_id)
        if profile is None:
            return
        self._current_conn_id = conn_id
        self._set_form_profile(profile)
        self._connect_with_profile(profile, conn_id)

    def _on_connection_list_context_menu(self, pos) -> None:
        item = self._connection_list.itemAt(pos)
        if not item:
            return
        conn_id = item.data(Qt.ItemDataRole.UserRole)
        if not conn_id:
            return
        profile = self._store.load(conn_id)
        if profile is None:
            return

        menu = QMenu(self)
        connect_action = menu.addAction("Connect")
        edit_action = menu.addAction("Edit")
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self._connection_list.viewport().mapToGlobal(pos))

        if action == connect_action:
            self._current_conn_id = conn_id
            self._set_form_profile(profile)
            self._connect_with_profile(profile, conn_id)
        elif action == edit_action:
            self._current_conn_id = conn_id
            self._set_form_profile(profile)
        elif action == duplicate_action:
            self._duplicate_profile(profile)
        elif action == delete_action:
            self._delete_profile(profile)

    def _on_new_clicked(self) -> None:
        self._current_conn_id = None
        self._connection_list.clearSelection()
        self._update_connection_item_selection_styles()
        self._set_form_profile({"driver_type": DriverType.POSTGRESQL.value, "port": 5432})
        self._name_input.setFocus()
        self._set_status("New connection", "normal")

    def _delete_profile(self, profile: dict[str, Any]) -> None:
        conn_id = profile.get("id")
        if not conn_id:
            return
        reply = QMessageBox.question(
            self,
            "Delete Connection",
            f"Delete '{profile.get('name', 'Unnamed')}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._store.delete(conn_id)
        if self._current_conn_id == conn_id:
            self._current_conn_id = None
        self._load_saved_connections()
        self._on_new_clicked()

    def _duplicate_profile(self, profile: dict[str, Any]) -> None:
        duplicate = dict(profile)
        duplicate.pop("id", None)
        original_name = duplicate.get("name", "Connection")
        duplicate["name"] = f"{original_name} (Copy)"
        new_conn_id = self._store.save(duplicate)
        self._current_conn_id = new_conn_id
        self._load_saved_connections()
        fresh = self._store.load(new_conn_id)
        if fresh:
            self._set_form_profile(fresh)
        self._set_status("Connection duplicated", "success")

    def _on_delete_clicked(self) -> None:
        if not self._current_conn_id:
            return
        profile = self._store.load(self._current_conn_id)
        if profile:
            self._delete_profile(profile)

    def _on_driver_changed(self) -> None:
        if self._selected_driver == DriverType.POSTGRESQL.value and self._port_input.value() == 3306:
            self._port_input.setValue(5432)
        elif self._selected_driver == DriverType.MYSQL.value and self._port_input.value() == 5432:
            self._port_input.setValue(3306)

    def _toggle_advanced(self) -> None:
        visible = not self._advanced_widget.isVisible()
        self._advanced_widget.setVisible(visible)
        self._advanced_toggle.setText(
            "Hide Advanced Options" if visible else "Advanced Options"
        )

    def _on_ssl_toggled(self, checked: bool) -> None:
        self._ssl_verify_checkbox.setEnabled(checked)

    def _on_ssh_toggled(self, checked: bool) -> None:
        self._ssh_fields_container.setVisible(checked)
        self._ssh_key_browse_btn.setEnabled(checked)

    def _on_browse_ssh_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SSH Private Key",
            self._ssh_key_input.text().strip() or "",
            "All Files (*)",
        )
        if path:
            self._ssh_key_input.setText(path)

    def _on_test_clicked(self) -> None:
        profile = self._get_form_profile()
        try:
            config = self._store.to_config(profile)
        except Exception as error:
            self._set_status(f"Validation Error: {error}", "error")
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
        self._set_status("Connection successful!" if success else "Connection failed", "success" if success else "error")
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
        self._set_status("Saved", "success")

    def _on_connect_clicked(self) -> None:
        profile = self._get_form_profile()
        if not profile["name"]:
            self._name_input.setFocus()
            self._set_status("Enter a connection name", "error")
            return
        self._current_conn_id = self._store.save(profile, self._current_conn_id)
        profile["id"] = self._current_conn_id
        self._load_saved_connections()
        self._connect_with_profile(profile, self._current_conn_id)

    def _connect_with_profile(
        self, profile: dict[str, Any], conn_id: str | None = None
    ) -> None:
        self._current_conn_id = conn_id or self._current_conn_id
        try:
            config = self._store.to_config(profile)
        except Exception as error:
            self._set_status(f"Error: {error}", "error")
            return

        if not self._current_conn_id:
            self._set_status("Connection ID is missing", "error")
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
        if self._current_conn_id and self._current_conn_id in self._manager.active_connections:
            self._manager.close_connection(self._current_conn_id)

    def _set_status(self, message: str, status_type: str) -> None:
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
