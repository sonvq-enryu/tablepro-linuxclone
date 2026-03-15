"""Connection dialog with two-panel connection manager UX."""

from typing import Any

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sshtunnel import SSHTunnelForwarder

from tablefree.db.config import ConnectionConfig, DriverType
from tablefree.db.connection_store import ConnectionStore
from tablefree.db.driver import DatabaseDriver
from tablefree.db.manager import ConnectionManager
from tablefree.db.mysql_driver import MySQLDriver
from tablefree.db.postgres_driver import PostgreSQLDriver
from tablefree.db.ssh_config import SSHAuthMethod
from tablefree.db.ssh_store import SSHProfileStore
from tablefree.resource_path import resources_dir
from tablefree.theme import current
from tablefree.widgets.ssh_profile_dialog import SSHProfileDialog
from tablefree.workers import QueryWorker


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
        self._ssh_store = SSHProfileStore()
        self._thread_pool = QThreadPool.globalInstance()

        self._active_driver: DatabaseDriver | None = None
        self._current_conn_id: str | None = None
        self._selected_driver: str = DriverType.POSTGRESQL.value
        self._driver_cards: dict[str, QPushButton] = {}
        self._profiles_by_id: dict[str, dict[str, Any]] = {}
        self._ssh_profiles_by_id: dict[str, dict[str, Any]] = {}

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
        right_layout.setSpacing(8)
        split_layout.addWidget(right_panel, stretch=1)

        self._form_scroll = QScrollArea()
        self._form_scroll.setObjectName("connection-form-scroll")
        self._form_scroll.setWidgetResizable(True)
        self._form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._form_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        form_container = QWidget()
        form_container.setObjectName("connection-form-scroll-content")
        scroll_layout = QVBoxLayout(form_container)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(12)
        self._form_scroll.setWidget(form_container)
        right_layout.addWidget(self._form_scroll, stretch=1)

        header_layout = QHBoxLayout()
        self._title_label = QLabel("New Connection")
        self._title_label.setObjectName("connection-dialog-title")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        scroll_layout.addLayout(header_layout)

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
        scroll_layout.addLayout(cards_layout)

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

        auth_labels = QHBoxLayout()
        user_label = QLabel("Username")
        user_label.setObjectName("form-label")
        pass_label = QLabel("Password")
        pass_label.setObjectName("form-label")
        auth_labels.addWidget(user_label, stretch=1)
        auth_labels.addWidget(pass_label, stretch=1)
        form_layout.addLayout(auth_labels)

        auth_row = QHBoxLayout()
        auth_row.setSpacing(8)
        self._user_input = QLineEdit()
        self._user_input.setObjectName("username-input")
        self._user_input.setPlaceholderText("username")
        auth_row.addWidget(self._user_input, stretch=1)

        pass_widget = QWidget()
        pass_widget.setObjectName("password-row")
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
        auth_row.addWidget(pass_widget, stretch=1)
        form_layout.addLayout(auth_row)

        db_label = QLabel("Database Name")
        db_label.setObjectName("form-label")
        form_layout.addWidget(db_label)
        self._db_input = QLineEdit()
        self._db_input.setObjectName("database-input")
        self._db_input.setPlaceholderText("database_name")
        form_layout.addWidget(self._db_input)

        scroll_layout.addLayout(form_layout)

        self._advanced_toggle = QPushButton("Advanced Options")
        self._advanced_toggle.setObjectName("advanced-toggle")
        self._advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._advanced_toggle.clicked.connect(self._toggle_advanced)
        scroll_layout.addWidget(self._advanced_toggle)

        self._advanced_widget = QWidget()
        self._advanced_widget.setObjectName("advanced-panel")
        self._advanced_widget.setVisible(False)
        adv_layout = QVBoxLayout(self._advanced_widget)
        adv_layout.setSpacing(8)
        adv_layout.setContentsMargins(0, 0, 0, 0)

        ssl_section = QWidget()
        ssl_section.setObjectName("advanced-section-card")
        ssl_section_layout = QVBoxLayout(ssl_section)
        ssl_section_layout.setContentsMargins(10, 10, 10, 8)
        ssl_section_layout.setSpacing(4)

        ssl_title = QLabel("SSL / TLS")
        ssl_title.setObjectName("advanced-section-title")
        ssl_section_layout.addWidget(ssl_title)
        ssl_subtitle = QLabel("Encrypt traffic between client and database server.")
        ssl_subtitle.setObjectName("advanced-section-subtitle")
        ssl_subtitle.setWordWrap(True)
        ssl_section_layout.addWidget(ssl_subtitle)

        self._ssl_checkbox = QCheckBox("Use SSL/TLS")
        self._ssl_checkbox.setObjectName("ssl-checkbox")
        self._ssl_checkbox.toggled.connect(self._on_ssl_toggled)
        ssl_section_layout.addWidget(self._ssl_checkbox)

        self._ssl_verify_checkbox = QCheckBox("Verify server certificate")
        self._ssl_verify_checkbox.setObjectName("ssl-verify-checkbox")
        self._ssl_verify_checkbox.setChecked(True)
        self._ssl_verify_row = QWidget()
        self._ssl_verify_row.setObjectName("advanced-suboption-row")
        ssl_verify_layout = QHBoxLayout(self._ssl_verify_row)
        ssl_verify_layout.setContentsMargins(26, 2, 0, 0)
        ssl_verify_layout.addWidget(self._ssl_verify_checkbox)
        ssl_verify_layout.addStretch()
        ssl_section_layout.addWidget(self._ssl_verify_row)

        adv_layout.addWidget(ssl_section)

        separator = QFrame()
        separator.setObjectName("advanced-separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        adv_layout.addWidget(separator)

        ssh_section = QWidget()
        ssh_section.setObjectName("advanced-section-card")
        ssh_section_layout = QVBoxLayout(ssh_section)
        ssh_section_layout.setContentsMargins(10, 10, 10, 8)
        ssh_section_layout.setSpacing(4)

        ssh_title = QLabel("SSH Tunnel")
        ssh_title.setObjectName("advanced-section-title")
        ssh_section_layout.addWidget(ssh_title)
        ssh_subtitle = QLabel("Route database traffic through a secure bastion host.")
        ssh_subtitle.setObjectName("advanced-section-subtitle")
        ssh_subtitle.setWordWrap(True)
        ssh_section_layout.addWidget(ssh_subtitle)

        self._ssh_checkbox = QCheckBox("Use SSH Tunnel")
        self._ssh_checkbox.setObjectName("ssh-checkbox")
        self._ssh_checkbox.toggled.connect(self._on_ssh_toggled)
        ssh_section_layout.addWidget(self._ssh_checkbox)

        self._ssh_fields_container = QWidget()
        self._ssh_fields_container.setObjectName("ssh-fields-container")
        ssh_fields_layout = QVBoxLayout(self._ssh_fields_container)
        ssh_fields_layout.setContentsMargins(16, 4, 0, 0)
        ssh_fields_layout.setSpacing(8)

        ssh_profile_label = QLabel("SSH Profile")
        ssh_profile_label.setObjectName("form-label")
        ssh_fields_layout.addWidget(ssh_profile_label)

        ssh_profile_row = QHBoxLayout()
        self._ssh_profile_combo = QComboBox()
        self._ssh_profile_combo.setObjectName("ssh-profile-combo")
        self._ssh_profile_combo.currentIndexChanged.connect(self._on_ssh_profile_changed)
        ssh_profile_row.addWidget(self._ssh_profile_combo, stretch=1)

        self._ssh_manage_btn = QPushButton("Manage Profiles...")
        self._ssh_manage_btn.setObjectName("ssh-manage-btn")
        self._ssh_manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ssh_manage_btn.clicked.connect(self._on_manage_ssh_profiles)
        ssh_profile_row.addWidget(self._ssh_manage_btn)
        ssh_fields_layout.addLayout(ssh_profile_row)

        self._ssh_summary_widget = QWidget()
        self._ssh_summary_widget.setObjectName("ssh-summary-widget")
        summary_layout = QVBoxLayout(self._ssh_summary_widget)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(2)

        self._ssh_summary_host = QLabel("")
        self._ssh_summary_user = QLabel("")
        self._ssh_summary_auth = QLabel("")
        for label in (
            self._ssh_summary_host,
            self._ssh_summary_user,
            self._ssh_summary_auth,
        ):
            label.setObjectName("form-label")
            summary_layout.addWidget(label)
        ssh_fields_layout.addWidget(self._ssh_summary_widget)

        ssh_section_layout.addWidget(self._ssh_fields_container)
        adv_layout.addWidget(ssh_section)
        scroll_layout.addWidget(self._advanced_widget)

        scroll_layout.addStretch()
        self._on_ssl_toggled(self._ssl_checkbox.isChecked())
        self._load_ssh_profiles()
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
            "ssh_profile_id": self._get_selected_ssh_profile_id(),
        }

    def _load_ssh_profiles(self, select_profile_id: str = "") -> None:
        self._ssh_profiles_by_id = {}
        profiles = self._ssh_store.load_all()
        self._ssh_profile_combo.blockSignals(True)
        self._ssh_profile_combo.clear()
        self._ssh_profile_combo.addItem("Select SSH profile...", "")
        for profile in profiles:
            profile_id = profile.get("id")
            if not profile_id:
                continue
            self._ssh_profiles_by_id[profile_id] = profile
            self._ssh_profile_combo.addItem(profile.get("name", "Unnamed"), profile_id)
        self._ssh_profile_combo.blockSignals(False)
        self._select_ssh_profile_in_combo(select_profile_id)

    def _get_selected_ssh_profile_id(self) -> str:
        if not self._ssh_checkbox.isChecked():
            return ""
        profile_id = self._ssh_profile_combo.currentData()
        if isinstance(profile_id, str):
            return profile_id
        return ""

    def _select_ssh_profile_in_combo(self, profile_id: str) -> None:
        for index in range(self._ssh_profile_combo.count()):
            if self._ssh_profile_combo.itemData(index) == profile_id:
                self._ssh_profile_combo.setCurrentIndex(index)
                self._update_ssh_summary()
                return
        self._ssh_profile_combo.setCurrentIndex(0)
        self._update_ssh_summary()

    def _on_ssh_profile_changed(self, _: int) -> None:
        self._update_ssh_summary()

    def _update_ssh_summary(self) -> None:
        profile_id = self._get_selected_ssh_profile_id()
        profile = self._ssh_profiles_by_id.get(profile_id)
        has_profile = profile is not None and self._ssh_checkbox.isChecked()
        self._ssh_summary_widget.setVisible(has_profile)
        if not has_profile:
            self._ssh_summary_host.setText("")
            self._ssh_summary_user.setText("")
            self._ssh_summary_auth.setText("")
            return

        auth_method = str(profile.get("auth_method", SSHAuthMethod.KEY.value))
        if auth_method == SSHAuthMethod.PASSWORD.value:
            auth_detail = "Password"
        else:
            key_path = str(profile.get("ssh_key_path", "")).strip()
            auth_detail = f"Key ({key_path})" if key_path else "Key"
        self._ssh_summary_host.setText(f"Host: {profile.get('ssh_host', '')}")
        self._ssh_summary_user.setText(f"User: {profile.get('ssh_user', '')}")
        self._ssh_summary_auth.setText(f"Auth: {auth_detail}")

    def _on_manage_ssh_profiles(self) -> None:
        dialog = SSHProfileDialog(self)
        dialog.profile_saved.connect(self._on_ssh_profile_saved)
        dialog.exec()

    def _on_ssh_profile_saved(self, profile_id: str) -> None:
        self._load_ssh_profiles(profile_id)

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
        icon_path = resources_dir() / "icons" / icon_name
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
        ssh_profile_id = str(profile.get("ssh_profile_id", "") or "")
        self._ssh_checkbox.setChecked(bool(ssh_profile_id))
        self._select_ssh_profile_in_combo(ssh_profile_id)
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
        self._ssh_profile_combo.setDisabled(disabled or not self._ssh_checkbox.isChecked())
        self._ssh_manage_btn.setDisabled(disabled or not self._ssh_checkbox.isChecked())

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
        self._ssh_fields_container.setProperty("active", checked)
        self._ssh_fields_container.style().unpolish(self._ssh_fields_container)
        self._ssh_fields_container.style().polish(self._ssh_fields_container)
        self._ssh_profile_combo.setEnabled(checked)
        self._ssh_manage_btn.setEnabled(checked)
        self._update_ssh_summary()

    def _on_test_clicked(self) -> None:
        profile = self._get_form_profile()
        try:
            config = self._store.to_config(profile)
        except Exception as error:
            self._set_status(f"Validation Error: {error}", "error")
            return

        self._set_ui_disabled(True)
        self._set_status("Testing connection...", "loading")

        ssh_profile_id = profile.get("ssh_profile_id") or None
        if self._ssh_checkbox.isChecked() and not ssh_profile_id:
            self._set_ui_disabled(False)
            self._set_status("Select an SSH profile", "error")
            return

        worker = QueryWorker(self._test_connection_task, config, ssh_profile_id)
        self._test_worker = worker
        worker.signals.finished.connect(self._on_test_finished)
        worker.signals.error.connect(self._on_test_error)
        self._thread_pool.start(worker)

    def _test_connection_task(
        self, config: ConnectionConfig, ssh_profile_id: str | None
    ) -> bool:
        driver_cls = (
            PostgreSQLDriver
            if config.driver_type == DriverType.POSTGRESQL
            else MySQLDriver
        )
        if not ssh_profile_id:
            driver = driver_cls(config)
            return driver.test_connection()

        ssh_data = self._ssh_store.load(ssh_profile_id)
        if ssh_data is None:
            raise ValueError(f"SSH profile '{ssh_profile_id}' not found")
        ssh_profile = self._ssh_store.to_ssh_profile(ssh_data)

        kwargs = {
            "ssh_address_or_host": (ssh_profile.ssh_host, ssh_profile.ssh_port),
            "ssh_username": ssh_profile.ssh_user,
            "remote_bind_address": (config.host, config.port),
        }
        if ssh_profile.auth_method == SSHAuthMethod.PASSWORD:
            kwargs["ssh_password"] = ssh_profile.ssh_password
        else:
            kwargs["ssh_pkey"] = ssh_profile.ssh_key_path
            if ssh_profile.ssh_key_passphrase:
                kwargs["ssh_private_key_password"] = ssh_profile.ssh_key_passphrase

        forwarder = SSHTunnelForwarder(**kwargs)
        try:
            forwarder.start()
            tunneled_config = ConnectionConfig(
                host="127.0.0.1",
                port=int(forwarder.local_bind_port),
                database=config.database,
                username=config.username,
                password=config.password,
                driver_type=config.driver_type,
                name=config.name,
                ssl=config.ssl,
                options=config.options,
            )
            driver = driver_cls(tunneled_config)
            return driver.test_connection()
        finally:
            try:
                forwarder.stop()
            except Exception:
                pass

    def _on_test_finished(self, success: bool) -> None:
        self._set_ui_disabled(False)
        self._set_status("Connection successful!" if success else "Connection failed", "success" if success else "error")
        self._test_worker = None

    def _on_test_error(self, error: Exception) -> None:
        self._set_ui_disabled(False)
        self._set_status(f"Error: {error}", "error")
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

        if self._ssh_checkbox.isChecked() and not (profile.get("ssh_profile_id") or ""):
            self._set_status("Select an SSH profile", "error")
            return

        self._set_ui_disabled(True)
        self._set_status("Connecting...", "loading")

        if self._current_conn_id in self._manager.active_connections:
            self._manager.close_connection(self._current_conn_id)

        worker = QueryWorker(
            self._manager.create_connection,
            self._current_conn_id,
            config,
            profile.get("ssh_profile_id") or None,
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
