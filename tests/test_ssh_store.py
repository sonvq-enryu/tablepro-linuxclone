"""Unit tests for SSHProfileStore."""

import json
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from tablefree.db.ssh_config import SSHAuthMethod
from tablefree.db.ssh_store import SSHProfileStore

APP = QApplication.instance()
if APP is None:
    APP = QApplication(["--platform", "offscreen"])


@pytest.fixture(autouse=True)
def mock_keyring():
    store: dict[str, str] = {}

    def mock_set(service, username, password):
        store[username] = password

    def mock_get(service, username):
        return store.get(username)

    def mock_delete(service, username):
        if username in store:
            del store[username]
            return
        import keyring.errors

        raise keyring.errors.PasswordDeleteError()

    with (
        patch("tablefree.db.ssh_store.keyring.set_password", side_effect=mock_set),
        patch("tablefree.db.ssh_store.keyring.get_password", side_effect=mock_get),
        patch("tablefree.db.ssh_store.keyring.delete_password", side_effect=mock_delete),
    ):
        yield store


def test_save_and_load_profile() -> None:
    store = SSHProfileStore()
    profile = {
        "name": "Prod Bastion",
        "ssh_host": "bastion.example.com",
        "ssh_port": 22,
        "ssh_user": "deploy",
        "auth_method": SSHAuthMethod.KEY.value,
        "ssh_key_path": "/tmp/id_rsa",
        "ssh_key_passphrase": "passphrase",
        "ssh_password": "",
    }
    profile_id = store.save(profile)
    loaded = store.load(profile_id)
    assert loaded is not None
    assert loaded["name"] == "Prod Bastion"
    assert loaded["ssh_host"] == "bastion.example.com"
    assert loaded["ssh_key_passphrase"] == "passphrase"


def test_load_all_sorted_by_name() -> None:
    store = SSHProfileStore()
    for existing in store.load_all():
        profile_id = existing.get("id")
        if profile_id:
            store.delete(profile_id)

    store.save({"name": "Zulu", "ssh_host": "z", "ssh_user": "u"})
    store.save({"name": "Alpha", "ssh_host": "a", "ssh_user": "u"})
    store.save({"name": "Beta", "ssh_host": "b", "ssh_user": "u"})
    names = [profile["name"] for profile in store.load_all()]
    assert names[:3] == ["Alpha", "Beta", "Zulu"]


def test_delete_profile() -> None:
    store = SSHProfileStore()
    profile_id = store.save({"name": "Tmp", "ssh_host": "tmp", "ssh_user": "u"})
    assert store.load(profile_id) is not None
    store.delete(profile_id)
    assert store.load(profile_id) is None


def test_to_ssh_profile_key_auth() -> None:
    store = SSHProfileStore()
    profile = store.to_ssh_profile(
        {
            "name": "Key Profile",
            "ssh_host": "host",
            "ssh_port": 22,
            "ssh_user": "deploy",
            "auth_method": SSHAuthMethod.KEY.value,
            "ssh_key_path": "/tmp/key",
            "ssh_key_passphrase": "secret",
        }
    )
    assert profile.auth_method == SSHAuthMethod.KEY
    assert profile.ssh_key_path == "/tmp/key"
    assert profile.ssh_key_passphrase == "secret"


def test_to_ssh_profile_password_auth() -> None:
    store = SSHProfileStore()
    profile = store.to_ssh_profile(
        {
            "name": "Password Profile",
            "ssh_host": "host",
            "ssh_port": 22,
            "ssh_user": "deploy",
            "auth_method": SSHAuthMethod.PASSWORD.value,
            "ssh_password": "pw",
        }
    )
    assert profile.auth_method == SSHAuthMethod.PASSWORD
    assert profile.ssh_password == "pw"


def test_secrets_stored_in_keyring(mock_keyring) -> None:
    store = SSHProfileStore()
    profile = {
        "name": "Secrets",
        "ssh_host": "host",
        "ssh_port": 22,
        "ssh_user": "deploy",
        "auth_method": SSHAuthMethod.PASSWORD.value,
        "ssh_password": "pw123",
        "ssh_key_passphrase": "phrase123",
        "ssh_key_path": "",
    }
    profile_id = store.save(profile)
    loaded = store.load(profile_id)
    assert loaded is not None
    assert loaded["ssh_password"] == "pw123"
    assert loaded["ssh_key_passphrase"] == "phrase123"

    store._settings.beginGroup(store._GROUP)
    raw = store._settings.value(profile_id, "")
    store._settings.endGroup()
    saved_payload = json.loads(raw)
    assert "ssh_password" not in saved_payload
    assert "ssh_key_passphrase" not in saved_payload
