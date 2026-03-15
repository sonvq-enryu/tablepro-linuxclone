"""Unit tests for ConnectionStore."""

import pytest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

# Need a QApplication for Qt-based tests.
APP = QApplication.instance()
if APP is None:
    APP = QApplication(["--platform", "offscreen"])

@pytest.fixture(autouse=True)
def mock_keyring():
    store = {}
    
    def mock_set(service, username, password):
        store[username] = password
        
    def mock_get(service, username):
        return store.get(username)
        
    def mock_delete(service, username):
        if username in store:
            del store[username]
        else:
            import keyring.errors
            raise keyring.errors.PasswordDeleteError()
            
    with patch("tablefree.db.connection_store.keyring.set_password", side_effect=mock_set), \
         patch("tablefree.db.connection_store.keyring.get_password", side_effect=mock_get), \
         patch("tablefree.db.connection_store.keyring.delete_password", side_effect=mock_delete):
        yield store

from tablefree.db.config import DriverType
from tablefree.db.connection_store import ConnectionStore


def test_save_and_load_profile() -> None:
    store = ConnectionStore()

    profile = {
        "name": "Test DB",
        "driver_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "username": "user",
        "password": "secret_password",
    }

    conn_id = store.save(profile.copy())
    assert conn_id is not None

    loaded = store.load(conn_id)
    assert loaded is not None
    assert loaded["name"] == "Test DB"
    assert loaded["password"] == "secret_password"
    assert "id" in loaded

    # Verify it converts to config properly
    config = store.to_config(loaded)
    assert config.name == "Test DB"
    assert config.password == "secret_password"
    assert config.driver_type == DriverType.POSTGRESQL


def test_delete_profile() -> None:
    store = ConnectionStore()
    profile = {
        "name": "To Delete",
        "driver_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "db",
        "username": "u",
        "password": "p",
    }
    conn_id = store.save(profile)
    assert store.load(conn_id) is not None

    store.delete(conn_id)
    assert store.load(conn_id) is None


def test_load_all_returns_multiple() -> None:
    store = ConnectionStore()

    # Setup fresh state by deleting all existing
    for p in store.load_all():
        store.delete(p["id"])

    store.save({
        "name": "A DB",
        "driver_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "db1",
        "username": "u1",
        "password": "p1",
    })

    store.save({
        "name": "B DB",
        "driver_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "db2",
        "username": "u2",
        "password": "p2",
    })

    profiles = store.load_all()
    assert len(profiles) >= 2

    # Verify we can find ours
    names = [p.get("name") for p in profiles]
    assert "A DB" in names
    assert "B DB" in names


def test_save_with_ssh_profile_id() -> None:
    store = ConnectionStore()
    profile = {
        "name": "SSH Linked DB",
        "driver_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "db",
        "username": "user",
        "password": "secret",
        "ssh_profile_id": "ssh-prod-1",
    }
    conn_id = store.save(profile.copy())
    loaded = store.load(conn_id)
    assert loaded is not None
    assert loaded.get("ssh_profile_id") == "ssh-prod-1"


def test_to_config_ignores_ssh_profile_id() -> None:
    store = ConnectionStore()
    profile = {
        "name": "Config DB",
        "driver_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "db",
        "username": "user",
        "password": "secret",
        "ssh_profile_id": "ssh-staging",
    }
    config = store.to_config(profile)
    assert config.name == "Config DB"
    assert config.driver_type == DriverType.MYSQL
