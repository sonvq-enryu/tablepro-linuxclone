"""Connection setup dialog."""

from typing import Any

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
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
    """Modal dialog for managing and establishing database connections."""

    def __init__(
        self, manager: ConnectionManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Database Connections")
        self.resize(700, 500)
        self.setObjectName("connection-dialog")

        self._manager = manager
        self._store = ConnectionStore()
        self._thread_pool = QThreadPool.globalInstance()

        self._active_driver: DatabaseDriver | None = None
        self._current_conn_id: str | None = None

        self._setup_ui()
        self._load_saved_connections()

    @property
    def active_driver(self) -> DatabaseDriver | None:
        """The successfully connected driver, or None."""
        return self._active_driver

    # ── UI Setup ─────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left Panel: Saved Connections
        left_panel = QWidget()
        left_panel.setObjectName("connection-list-panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)

        left_label = QLabel("Saved Connections")
        left_label.setObjectName("connection-list-title")
        left_layout.addWidget(left_label)

        self._conn_list = QListWidget()
        self._conn_list.setObjectName("connection-list")
        self._conn_list.itemSelectionChanged.connect(self._on_connection_selected)
        left_layout.addWidget(self._conn_list)

        btn_layout = QHBoxLayout()
        self._new_btn = QPushButton("+ New")
        self._new_btn.clicked.connect(self._on_new_clicked)
        self._delete_btn = QPushButton("✕ Delete")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self._new_btn)
        btn_layout.addWidget(self._delete_btn)
        left_layout.addLayout(btn_layout)

        left_panel.setFixedWidth(220)
        layout.addWidget(left_panel)

        # ── Right Panel: Connection Form
        right_panel = QWidget()
        right_panel.setObjectName("connection-form-panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 24, 24, 24)

        form_title = QLabel("Connection Settings")
        form_title.setObjectName("connection-form-title")
        right_layout.addWidget(form_title)

        form_layout = QFormLayout()

        self._name_input = QLineEdit()
        form_layout.addRow("Name:", self._name_input)

        self._driver_combo = QComboBox()
        self._driver_combo.addItem("PostgreSQL", DriverType.POSTGRESQL.value)
        self._driver_combo.addItem("MySQL", DriverType.MYSQL.value)
        self._driver_combo.currentIndexChanged.connect(self._on_driver_changed)
        form_layout.addRow("Driver:", self._driver_combo)

        self._host_input = QLineEdit("localhost")
        form_layout.addRow("Host:", self._host_input)

        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(5432)
        form_layout.addRow("Port:", self._port_input)

        self._db_input = QLineEdit()
        form_layout.addRow("Database:", self._db_input)

        self._user_input = QLineEdit()
        form_layout.addRow("Username:", self._user_input)

        self._pass_input = QLineEdit()
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self._pass_input)

        right_layout.addLayout(form_layout)
        right_layout.addStretch()

        # Action Buttons
        actions_layout = QHBoxLayout()
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("conn-status-label")
        actions_layout.addWidget(self._status_label)
        actions_layout.addStretch()

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setObjectName("dialog-action-btn")
        self._test_btn.clicked.connect(self._on_test_clicked)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("dialog-action-btn")
        self._save_btn.clicked.connect(self._on_save_clicked)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("dialog-action-btn-primary")
        self._connect_btn.clicked.connect(self._on_connect_clicked)

        actions_layout.addWidget(self._test_btn)
        actions_layout.addWidget(self._save_btn)
        actions_layout.addWidget(self._connect_btn)

        right_layout.addLayout(actions_layout)
        layout.addWidget(right_panel)

    # ── State Management ─────────────────────────────────────

    def _load_saved_connections(self) -> None:
        self._conn_list.clear()
        profiles = self._store.load_all()
        for p in profiles:
            item = QListWidgetItem(p.get("name", "Unnamed"))
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._conn_list.addItem(item)

    def _get_form_profile(self) -> dict[str, Any]:
        return {
            "name": self._name_input.text().strip(),
            "driver_type": self._driver_combo.currentData(),
            "host": self._host_input.text().strip(),
            "port": self._port_input.value(),
            "database": self._db_input.text().strip(),
            "username": self._user_input.text().strip(),
            "password": self._pass_input.text(),
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

    def _set_ui_disabled(self, disabled: bool) -> None:
        self._test_btn.setDisabled(disabled)
        self._save_btn.setDisabled(disabled)
        self._connect_btn.setDisabled(disabled)
        self._conn_list.setDisabled(disabled)
        self._new_btn.setDisabled(disabled)
        self._delete_btn.setDisabled(disabled)

        # also disable inputs
        self._name_input.setDisabled(disabled)
        self._driver_combo.setDisabled(disabled)
        self._host_input.setDisabled(disabled)
        self._port_input.setDisabled(disabled)
        self._db_input.setDisabled(disabled)
        self._user_input.setDisabled(disabled)
        self._pass_input.setDisabled(disabled)

    # ── Slots ────────────────────────────────────────────────

    def _on_connection_selected(self) -> None:
        items = self._conn_list.selectedItems()
        if not items:
            return
        profile = items[0].data(Qt.ItemDataRole.UserRole)
        self._current_conn_id = profile.get("id")
        self._set_form_profile(profile)
        self._status_label.setText("Ready")
        self._status_label.setStyleSheet("")

    def _on_new_clicked(self) -> None:
        self._conn_list.clearSelection()
        self._current_conn_id = None
        self._set_form_profile({"driver_type": DriverType.POSTGRESQL.value})
        self._name_input.setFocus()
        self._status_label.setText("Ready")
        self._status_label.setStyleSheet("")

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
                f"Are you sure you want to delete '{profile.get('name')}'?",
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

    def _on_test_clicked(self) -> None:
        profile = self._get_form_profile()
        try:
            config = self._store.to_config(profile)
        except Exception as e:
            self._status_label.setText("❌ Validation Error")
            self._status_label.setStyleSheet("color: #E06C75;")
            return

        self._set_ui_disabled(True)
        self._status_label.setText("Testing...")
        self._status_label.setStyleSheet("color: #61AFEF;")

        # Create driver instance for testing (don't register with manager yet)
        driver_cls = (
            PostgreSQLDriver
            if config.driver_type == DriverType.POSTGRESQL
            else MySQLDriver
        )
        self._test_driver = driver_cls(config)

        worker = QueryWorker(self._test_driver.test_connection)

        # Store worker reference to prevent garbage collection
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
            self._status_label.setText("✅ Connection Successful")
            self._status_label.setStyleSheet("color: #98C379;")
        else:
            self._status_label.setText("❌ Connection Failed")
            self._status_label.setStyleSheet("color: #E06C75;")
        # Clean up
        self._test_driver = None
        self._test_worker = None

    def _on_test_error(self, error: Exception, driver: DatabaseDriver) -> None:
        self._set_ui_disabled(False)
        self._status_label.setText(f"❌ Error: {error}")
        self._status_label.setStyleSheet("color: #E06C75;")
        # Clean up
        self._test_driver = None
        self._test_worker = None

    def _on_save_clicked(self) -> None:
        profile = self._get_form_profile()
        if not profile["name"]:
            QMessageBox.warning(self, "Validation", "Connection Name is required.")
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

        self._status_label.setText("✅ Saved")
        self._status_label.setStyleSheet("color: #98C379;")

    def _on_connect_clicked(self) -> None:
        profile = self._get_form_profile()
        if not profile["name"]:
            QMessageBox.warning(self, "Validation", "Connection Name is required.")
            return

        self._current_conn_id = self._store.save(profile, self._current_conn_id)
        try:
            config = self._store.to_config(profile)
        except Exception:
            return

        self._set_ui_disabled(True)
        self._status_label.setText("Connecting...")
        self._status_label.setStyleSheet("color: #61AFEF;")

        # Close existing connection if we're reconnecting
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
        self._status_label.setText(f"❌ Connection Error: {error}")
        self._status_label.setStyleSheet("color: #E06C75;")

        # Cleanup failed connection from manager if it got registered somehow
        if (
            self._current_conn_id
            and self._current_conn_id in self._manager.active_connections
        ):
            self._manager.close_connection(self._current_conn_id)
