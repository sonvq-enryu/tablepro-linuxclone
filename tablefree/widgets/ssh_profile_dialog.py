"""Dialog for creating and managing SSH tunnel profiles."""
from typing import Any

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sshtunnel import SSHTunnelForwarder

from tablefree.db.ssh_config import SSHAuthMethod
from tablefree.db.ssh_store import SSHProfileStore
from tablefree.workers import QueryWorker


class SSHProfileDialog(QDialog):
    """Standalone dialog for SSH profile CRUD operations."""

    profile_saved = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SSH Profiles")
        self.resize(860, 560)
        self.setObjectName("ssh-profile-dialog")

        self._store = SSHProfileStore()
        self._thread_pool = QThreadPool.globalInstance()

        self._current_profile_id: str | None = None
        self._profiles_by_id: dict[str, dict[str, Any]] = {}
        self._test_worker: QueryWorker | None = None

        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        split = QHBoxLayout()
        split.setSpacing(14)
        root.addLayout(split, stretch=1)

        left_panel = QWidget()
        left_panel.setObjectName("connection-list-panel")
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        left_title = QLabel("SSH Profiles")
        left_title.setObjectName("connection-list-title")
        left_layout.addWidget(left_title)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("connection-search")
        self._search_input.setPlaceholderText("Search profiles...")
        self._search_input.textChanged.connect(self._refresh_profile_list)
        left_layout.addWidget(self._search_input)

        self._profile_list = QListWidget()
        self._profile_list.setObjectName("ssh-profile-list")
        self._profile_list.itemSelectionChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self._profile_list, stretch=1)

        self._new_btn = QPushButton("+ New Profile")
        self._new_btn.setObjectName("connection-new-btn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self._on_new_clicked)
        left_layout.addWidget(self._new_btn)
        split.addWidget(left_panel)

        right_panel = QWidget()
        right_panel.setObjectName("ssh-profile-form")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        split.addWidget(right_panel, stretch=1)

        title = QLabel("SSH Profile")
        title.setObjectName("connection-dialog-title")
        right_layout.addWidget(title)

        name_label = QLabel("Profile Name")
        name_label.setObjectName("form-label")
        right_layout.addWidget(name_label)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g., Production Bastion")
        right_layout.addWidget(self._name_input)

        host_port_labels = QHBoxLayout()
        host_label = QLabel("SSH Host")
        host_label.setObjectName("form-label")
        port_label = QLabel("SSH Port")
        port_label.setObjectName("form-label")
        host_port_labels.addWidget(host_label, stretch=3)
        host_port_labels.addWidget(port_label, stretch=1)
        right_layout.addLayout(host_port_labels)

        host_port_row = QHBoxLayout()
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("bastion.example.com")
        host_port_row.addWidget(self._host_input, stretch=3)
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(22)
        host_port_row.addWidget(self._port_input, stretch=1)
        right_layout.addLayout(host_port_row)

        user_label = QLabel("SSH User")
        user_label.setObjectName("form-label")
        right_layout.addWidget(user_label)
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("deploy")
        right_layout.addWidget(self._user_input)

        auth_label = QLabel("Auth Method")
        auth_label.setObjectName("form-label")
        right_layout.addWidget(auth_label)
        auth_row = QWidget()
        auth_row.setObjectName("auth-method-group")
        auth_row_layout = QHBoxLayout(auth_row)
        auth_row_layout.setContentsMargins(8, 6, 8, 6)
        auth_row_layout.setSpacing(12)
        self._auth_group = QButtonGroup(self)
        self._auth_key_radio = QRadioButton("Key")
        self._auth_password_radio = QRadioButton("Password")
        self._auth_group.addButton(self._auth_key_radio)
        self._auth_group.addButton(self._auth_password_radio)
        self._auth_key_radio.setChecked(True)
        self._auth_key_radio.toggled.connect(self._on_auth_method_changed)
        auth_row_layout.addWidget(self._auth_key_radio)
        auth_row_layout.addWidget(self._auth_password_radio)
        auth_row_layout.addStretch()
        right_layout.addWidget(auth_row)

        self._key_fields = QWidget()
        key_layout = QVBoxLayout(self._key_fields)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(8)

        key_path_label = QLabel("Key Path")
        key_path_label.setObjectName("form-label")
        key_layout.addWidget(key_path_label)
        key_path_row = QHBoxLayout()
        self._key_path_input = QLineEdit()
        self._key_path_input.setPlaceholderText("~/.ssh/id_rsa")
        key_path_row.addWidget(self._key_path_input, stretch=1)
        self._key_browse_btn = QPushButton("Browse...")
        self._key_browse_btn.setObjectName("ssh-manage-btn")
        self._key_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._key_browse_btn.clicked.connect(self._on_browse_key)
        key_path_row.addWidget(self._key_browse_btn)
        key_layout.addLayout(key_path_row)

        key_passphrase_label = QLabel("Passphrase")
        key_passphrase_label.setObjectName("form-label")
        key_layout.addWidget(key_passphrase_label)
        self._key_passphrase_input = QLineEdit()
        self._key_passphrase_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_layout.addWidget(self._key_passphrase_input)

        right_layout.addWidget(self._key_fields)

        self._password_fields = QWidget()
        password_layout = QVBoxLayout(self._password_fields)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(8)
        password_label = QLabel("SSH Password")
        password_label.setObjectName("form-label")
        password_layout.addWidget(password_label)
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self._password_input)
        right_layout.addWidget(self._password_fields)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("conn-status-label")
        right_layout.addWidget(self._status_label)
        right_layout.addStretch()

        actions = QHBoxLayout()
        self._test_btn = QPushButton("Test Tunnel")
        self._test_btn.setObjectName("dialog-action-btn-secondary")
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.clicked.connect(self._on_test_tunnel_clicked)
        actions.addWidget(self._test_btn)
        actions.addStretch()

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("dialog-action-btn-cancel")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        actions.addWidget(self._delete_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialog-action-btn-cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("dialog-action-btn-primary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save_clicked)
        actions.addWidget(save_btn)
        right_layout.addLayout(actions)

        self._on_auth_method_changed()

    def _load_profiles(self, select_profile_id: str | None = None) -> None:
        self._profiles_by_id = {}
        for profile in self._store.load_all():
            profile_id = profile.get("id")
            if profile_id:
                self._profiles_by_id[profile_id] = profile
        self._refresh_profile_list()
        if select_profile_id:
            self._select_profile(select_profile_id)
            return
        if self._current_profile_id:
            self._select_profile(self._current_profile_id)
            return
        self._on_new_clicked()

    def _refresh_profile_list(self) -> None:
        query = self._search_input.text().strip().lower()
        self._profile_list.blockSignals(True)
        self._profile_list.clear()
        for profile in self._store.load_all():
            profile_id = profile.get("id")
            if not profile_id:
                continue
            name = str(profile.get("name", "Unnamed"))
            host = str(profile.get("ssh_host", ""))
            if query and query not in f"{name} {host}".lower():
                continue
            item = QListWidgetItem(f"{name}  ({host})")
            item.setData(Qt.ItemDataRole.UserRole, profile_id)
            self._profile_list.addItem(item)
        self._profile_list.blockSignals(False)

    def _select_profile(self, profile_id: str) -> None:
        for index in range(self._profile_list.count()):
            item = self._profile_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == profile_id:
                self._profile_list.setCurrentItem(item)
                return

    def _on_profile_selected(self) -> None:
        item = self._profile_list.currentItem()
        if item is None:
            return
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        if not profile_id:
            return
        profile = self._store.load(profile_id)
        if profile is None:
            return
        self._current_profile_id = profile_id
        self._set_form_profile(profile)

    def _on_new_clicked(self) -> None:
        self._current_profile_id = None
        self._profile_list.clearSelection()
        self._set_form_profile(
            {
                "name": "",
                "ssh_host": "",
                "ssh_port": 22,
                "ssh_user": "",
                "auth_method": SSHAuthMethod.KEY.value,
                "ssh_key_path": "",
                "ssh_key_passphrase": "",
                "ssh_password": "",
            }
        )

    def _on_browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select SSH Private Key", "", "All Files (*)")
        if path:
            self._key_path_input.setText(path)

    def _on_auth_method_changed(self) -> None:
        use_key = self._auth_key_radio.isChecked()
        self._key_fields.setVisible(use_key)
        self._password_fields.setVisible(not use_key)

    def _get_form_profile(self) -> dict[str, Any]:
        return {
            "name": self._name_input.text().strip(),
            "ssh_host": self._host_input.text().strip(),
            "ssh_port": self._port_input.value(),
            "ssh_user": self._user_input.text().strip(),
            "auth_method": (
                SSHAuthMethod.KEY.value
                if self._auth_key_radio.isChecked()
                else SSHAuthMethod.PASSWORD.value
            ),
            "ssh_key_path": self._key_path_input.text().strip(),
            "ssh_key_passphrase": self._key_passphrase_input.text(),
            "ssh_password": self._password_input.text(),
        }

    def _set_form_profile(self, profile: dict[str, Any]) -> None:
        self._name_input.setText(str(profile.get("name", "")))
        self._host_input.setText(str(profile.get("ssh_host", "")))
        self._port_input.setValue(int(profile.get("ssh_port", 22) or 22))
        self._user_input.setText(str(profile.get("ssh_user", "")))
        auth_method = str(profile.get("auth_method", SSHAuthMethod.KEY.value))
        self._auth_key_radio.setChecked(auth_method == SSHAuthMethod.KEY.value)
        self._auth_password_radio.setChecked(auth_method == SSHAuthMethod.PASSWORD.value)
        self._key_path_input.setText(str(profile.get("ssh_key_path", "")))
        self._key_passphrase_input.setText(str(profile.get("ssh_key_passphrase", "")))
        self._password_input.setText(str(profile.get("ssh_password", "")))
        self._delete_btn.setEnabled(self._current_profile_id is not None)
        self._on_auth_method_changed()

    def _validate_profile(self, profile: dict[str, Any]) -> str | None:
        if not profile["name"]:
            return "Profile name is required"
        if not profile["ssh_host"]:
            return "SSH host is required"
        if not profile["ssh_user"]:
            return "SSH user is required"
        if profile["auth_method"] == SSHAuthMethod.KEY.value and not profile["ssh_key_path"]:
            return "Key path is required for key auth"
        if (
            profile["auth_method"] == SSHAuthMethod.PASSWORD.value
            and not profile["ssh_password"]
        ):
            return "Password is required for password auth"
        return None

    def _on_save_clicked(self) -> None:
        profile = self._get_form_profile()
        error = self._validate_profile(profile)
        if error:
            self._set_status(error, "error")
            return
        profile_id = self._store.save(profile, self._current_profile_id)
        self._current_profile_id = profile_id
        self._load_profiles(select_profile_id=profile_id)
        self._set_status("Profile saved", "success")
        self.profile_saved.emit(profile_id)

    def _on_delete_clicked(self) -> None:
        if not self._current_profile_id:
            return
        profile_name = self._name_input.text().strip() or "this profile"
        reply = QMessageBox.question(
            self,
            "Delete SSH Profile",
            f"Delete '{profile_name}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._store.delete(self._current_profile_id)
        self._current_profile_id = None
        self._load_profiles()
        self._set_status("Profile deleted", "success")
        self.profile_saved.emit("")

    def _on_test_tunnel_clicked(self) -> None:
        profile = self._get_form_profile()
        error = self._validate_profile(profile)
        if error:
            self._set_status(error, "error")
            return
        self._set_ui_disabled(True)
        self._set_status("Testing tunnel...", "loading")
        worker = QueryWorker(self._test_tunnel, profile)
        self._test_worker = worker
        worker.signals.finished.connect(self._on_test_finished)
        worker.signals.error.connect(self._on_test_error)
        self._thread_pool.start(worker)

    def _test_tunnel(self, profile_data: dict[str, Any]) -> bool:
        profile = self._store.to_ssh_profile(profile_data)
        kwargs = {
            "ssh_address_or_host": (profile.ssh_host, profile.ssh_port),
            "ssh_username": profile.ssh_user,
            "remote_bind_address": ("127.0.0.1", 22),
        }
        if profile.auth_method == SSHAuthMethod.PASSWORD:
            kwargs["ssh_password"] = profile.ssh_password
        else:
            kwargs["ssh_pkey"] = profile.ssh_key_path
            if profile.ssh_key_passphrase:
                kwargs["ssh_private_key_password"] = profile.ssh_key_passphrase

        forwarder = SSHTunnelForwarder(**kwargs)
        try:
            forwarder.start()
            return True
        finally:
            try:
                forwarder.stop()
            except Exception:
                pass

    def _on_test_finished(self, success: bool) -> None:
        self._set_ui_disabled(False)
        self._test_worker = None
        self._set_status("Tunnel is reachable" if success else "Tunnel test failed", "success" if success else "error")

    def _on_test_error(self, error: Exception) -> None:
        self._set_ui_disabled(False)
        self._test_worker = None
        self._set_status(f"Error: {error}", "error")

    def _set_ui_disabled(self, disabled: bool) -> None:
        self._search_input.setDisabled(disabled)
        self._profile_list.setDisabled(disabled)
        self._new_btn.setDisabled(disabled)
        self._delete_btn.setDisabled(disabled or self._current_profile_id is None)
        self._test_btn.setDisabled(disabled)

        for widget in (
            self._name_input,
            self._host_input,
            self._port_input,
            self._user_input,
            self._auth_key_radio,
            self._auth_password_radio,
            self._key_path_input,
            self._key_passphrase_input,
            self._password_input,
            self._key_browse_btn,
        ):
            widget.setDisabled(disabled)

    def _set_status(self, message: str, status: str) -> None:
        self._status_label.setText(message)
        if status == "error":
            self._status_label.setStyleSheet("color: #ef4444;")
        elif status == "success":
            self._status_label.setStyleSheet("color: #22c55e;")
        elif status == "loading":
            self._status_label.setStyleSheet("color: #3b82f6;")
        else:
            self._status_label.setStyleSheet("")
