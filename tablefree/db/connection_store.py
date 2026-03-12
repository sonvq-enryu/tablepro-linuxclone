"""Connection profile storage using QSettings and keyring."""

import json
import uuid

import keyring
import keyring.errors
from PySide6.QtCore import QSettings

from tablefree.db.config import ConnectionConfig, DriverType


class ConnectionStore:
    """Manages saving and loading database connection profiles.

    Stores metadata (host, port, username, database) in QSettings,
    and sensitive passwords securely in the system keyring.
    """

    SERVICE_NAME = "TableFree"
    _GROUP = "connections"

    def __init__(self) -> None:
        self._settings = QSettings()

    def save(self, profile: dict, connection_id: str | None = None) -> str:
        """Save a connection profile.

        If *connection_id* is missing, a new one is generated.

        Args:
            profile: A dictionary containing connection details.
                Requires: name, driver_type, host, port, database, username.
                Optional: password (stored in keyring).
            connection_id: The ID to update, or None to create new.

        Returns:
            The connection_id used.
        """
        if not connection_id:
            connection_id = str(uuid.uuid4())

        # Extract password to store securely
        password = profile.pop("password", None)

        self._settings.beginGroup(self._GROUP)
        self._settings.setValue(connection_id, json.dumps(profile))
        self._settings.endGroup()

        if password is not None:
            keyring.set_password(self.SERVICE_NAME, connection_id, password)

        # Put password back into dict for the caller
        if password is not None:
            profile["password"] = password
        profile["id"] = connection_id

        return connection_id

    def load_all(self) -> list[dict]:
        """Load all saved connection profiles.

        Returns:
            A list of profile dictionaries, including the 'id' and 'password'.
        """
        profiles = []
        self._settings.beginGroup(self._GROUP)

        for conn_id in self._settings.childKeys():
            data_str = self._settings.value(conn_id, "")
            if not data_str:
                continue

            try:
                profile = json.loads(data_str)
                profile["id"] = conn_id

                # Retrieve password from keyring
                password = keyring.get_password(self.SERVICE_NAME, conn_id)
                if password is not None:
                    profile["password"] = password
                else:
                    profile["password"] = ""

                profiles.append(profile)
            except json.JSONDecodeError:
                pass

        self._settings.endGroup()

        # Sort by name alphabetically
        profiles.sort(key=lambda p: p.get("name", "").lower())
        return profiles

    def load(self, connection_id: str) -> dict | None:
        """Load a specific connection profile by ID."""
        self._settings.beginGroup(self._GROUP)
        data_str = self._settings.value(connection_id, "")
        self._settings.endGroup()

        if not data_str:
            return None

        try:
            profile = json.loads(data_str)
            profile["id"] = connection_id

            password = keyring.get_password(self.SERVICE_NAME, connection_id)
            if password is not None:
                profile["password"] = password
            else:
                profile["password"] = ""

            return profile
        except json.JSONDecodeError:
            return None

    def delete(self, connection_id: str) -> None:
        """Delete a connection profile by ID from QSettings and keyring."""
        self._settings.beginGroup(self._GROUP)
        self._settings.remove(connection_id)
        self._settings.endGroup()

        try:
            keyring.delete_password(self.SERVICE_NAME, connection_id)
        except keyring.errors.PasswordDeleteError:
            # It's fine if the password wasn't in the keyring
            pass

    def to_config(self, profile: dict) -> ConnectionConfig:
        """Convert a profile dictionary to a ConnectionConfig object.

        Raises:
            KeyError: if required keys are missing.
            ValueError: if driver_type is invalid.
        """
        driver_type = DriverType(profile["driver_type"])

        return ConnectionConfig(
            host=profile["host"],
            port=int(profile["port"]),
            database=profile["database"],
            username=profile["username"],
            password=profile.get("password", ""),
            driver_type=driver_type,
            name=profile.get("name", ""),
        )
