"""SSH profile storage using QSettings and keyring."""

import json
import uuid
from typing import Any

import keyring
import keyring.errors
from PySide6.QtCore import QSettings

from tablefree.db.ssh_config import SSHAuthMethod, SSHProfile


class SSHProfileStore:
    """Persists SSH tunnel profiles with secrets in keyring."""

    SERVICE_NAME = "TableFree-SSH"
    _GROUP = "ssh_profiles"

    def __init__(self) -> None:
        self._settings = QSettings()

    def save(self, profile: dict, profile_id: str | None = None) -> str:
        """Save profile metadata to QSettings and secrets to keyring."""
        if not profile_id:
            profile_id = str(uuid.uuid4())

        auth_value = profile.get("auth_method", SSHAuthMethod.KEY.value)
        if isinstance(auth_value, SSHAuthMethod):
            auth_value = auth_value.value

        payload = {
            "name": profile.get("name", "").strip(),
            "ssh_host": profile.get("ssh_host", "").strip(),
            "ssh_port": int(profile.get("ssh_port", 22) or 22),
            "ssh_user": profile.get("ssh_user", "").strip(),
            "auth_method": auth_value,
            "ssh_key_path": profile.get("ssh_key_path", "").strip(),
        }

        self._settings.beginGroup(self._GROUP)
        self._settings.setValue(profile_id, json.dumps(payload))
        self._settings.endGroup()

        self._set_or_clear_secret(profile_id, "password", profile.get("ssh_password", ""))
        self._set_or_clear_secret(
            profile_id, "passphrase", profile.get("ssh_key_passphrase", "")
        )

        return profile_id

    def load_all(self) -> list[dict]:
        """Load all SSH profiles sorted by name."""
        profiles: list[dict[str, Any]] = []
        self._settings.beginGroup(self._GROUP)
        for profile_id in self._settings.childKeys():
            profile = self._load_profile_in_group(profile_id)
            if profile is not None:
                profiles.append(profile)
        self._settings.endGroup()
        profiles.sort(key=lambda p: str(p.get("name", "")).lower())
        return profiles

    def load(self, profile_id: str) -> dict | None:
        """Load one SSH profile by id."""
        self._settings.beginGroup(self._GROUP)
        profile = self._load_profile_in_group(profile_id)
        self._settings.endGroup()
        return profile

    def delete(self, profile_id: str) -> None:
        """Delete profile metadata and all saved secrets."""
        self._settings.beginGroup(self._GROUP)
        self._settings.remove(profile_id)
        self._settings.endGroup()
        self._delete_secret(profile_id, "password")
        self._delete_secret(profile_id, "passphrase")

    def to_ssh_profile(self, data: dict) -> SSHProfile:
        """Convert dictionary payload to immutable SSHProfile."""
        auth_method = SSHAuthMethod(data.get("auth_method", SSHAuthMethod.KEY.value))
        return SSHProfile(
            name=str(data.get("name", "")),
            ssh_host=str(data.get("ssh_host", "")),
            ssh_port=int(data.get("ssh_port", 22) or 22),
            ssh_user=str(data.get("ssh_user", "")),
            auth_method=auth_method,
            ssh_password=str(data.get("ssh_password", "")),
            ssh_key_path=str(data.get("ssh_key_path", "")),
            ssh_key_passphrase=str(data.get("ssh_key_passphrase", "")),
        )

    def _load_profile_in_group(self, profile_id: str) -> dict | None:
        data_str = self._settings.value(profile_id, "")
        if not data_str:
            return None

        try:
            profile = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        profile["id"] = profile_id
        profile["ssh_password"] = self._get_secret(profile_id, "password")
        profile["ssh_key_passphrase"] = self._get_secret(profile_id, "passphrase")
        return profile

    def _secret_key(self, profile_id: str, suffix: str) -> str:
        return f"{profile_id}:{suffix}"

    def _get_secret(self, profile_id: str, suffix: str) -> str:
        value = keyring.get_password(self.SERVICE_NAME, self._secret_key(profile_id, suffix))
        return value or ""

    def _set_or_clear_secret(self, profile_id: str, suffix: str, value: str) -> None:
        if value:
            keyring.set_password(
                self.SERVICE_NAME, self._secret_key(profile_id, suffix), value
            )
            return
        self._delete_secret(profile_id, suffix)

    def _delete_secret(self, profile_id: str, suffix: str) -> None:
        try:
            keyring.delete_password(
                self.SERVICE_NAME, self._secret_key(profile_id, suffix)
            )
        except keyring.errors.PasswordDeleteError:
            pass
