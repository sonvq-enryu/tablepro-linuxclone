"""Unit tests for SSHTunnelManager."""

from unittest.mock import Mock, patch

import pytest

from tablefree.db.ssh_config import SSHAuthMethod, SSHProfile
from tablefree.db.ssh_tunnel_manager import SSHTunnelManager


def _profile() -> SSHProfile:
    return SSHProfile(
        name="Prod",
        ssh_host="bastion.example.com",
        ssh_port=22,
        ssh_user="deploy",
        auth_method=SSHAuthMethod.KEY,
        ssh_key_path="/tmp/id_rsa",
    )


def _mock_forwarder(local_port: int = 10022) -> Mock:
    forwarder = Mock()
    forwarder.local_bind_port = local_port
    forwarder.is_active = True
    return forwarder


def test_open_tunnel_returns_local_bind() -> None:
    manager = SSHTunnelManager()
    forwarder = _mock_forwarder(12000)
    with patch(
        "tablefree.db.ssh_tunnel_manager.SSHTunnelForwarder", return_value=forwarder
    ):
        host, port = manager.open_tunnel(_profile(), "db.internal", 5432)
    assert host == "127.0.0.1"
    assert port == 12000
    forwarder.start.assert_called_once()


def test_open_tunnel_reuses_existing() -> None:
    manager = SSHTunnelManager()
    forwarder = _mock_forwarder(13000)
    with patch(
        "tablefree.db.ssh_tunnel_manager.SSHTunnelForwarder", return_value=forwarder
    ) as ctor:
        manager.open_tunnel(_profile(), "db.internal", 5432)
        manager.open_tunnel(_profile(), "db.internal", 5432)
    ctor.assert_called_once()


def test_close_tunnel_decrements_ref() -> None:
    manager = SSHTunnelManager()
    forwarder = _mock_forwarder(14000)
    with patch(
        "tablefree.db.ssh_tunnel_manager.SSHTunnelForwarder", return_value=forwarder
    ):
        profile = _profile()
        manager.open_tunnel(profile, "db.internal", 5432)
        manager.open_tunnel(profile, "db.internal", 5432)
        manager.close_tunnel(profile, "db.internal", 5432)
    forwarder.stop.assert_not_called()


def test_close_tunnel_stops_at_zero_refs() -> None:
    manager = SSHTunnelManager()
    forwarder = _mock_forwarder(15000)
    with patch(
        "tablefree.db.ssh_tunnel_manager.SSHTunnelForwarder", return_value=forwarder
    ):
        profile = _profile()
        manager.open_tunnel(profile, "db.internal", 5432)
        manager.close_tunnel(profile, "db.internal", 5432)
    forwarder.stop.assert_called_once()


def test_close_all() -> None:
    manager = SSHTunnelManager()
    forwarders = [_mock_forwarder(16000), _mock_forwarder(16001), _mock_forwarder(16002)]
    with patch(
        "tablefree.db.ssh_tunnel_manager.SSHTunnelForwarder", side_effect=forwarders
    ):
        profile = _profile()
        manager.open_tunnel(profile, "db1.internal", 5432)
        manager.open_tunnel(profile, "db2.internal", 5432)
        manager.open_tunnel(profile, "db3.internal", 5432)
        manager.close_all()
    for forwarder in forwarders:
        forwarder.stop.assert_called_once()


def test_open_tunnel_failure_raises() -> None:
    manager = SSHTunnelManager()
    forwarder = _mock_forwarder(17000)
    forwarder.start.side_effect = RuntimeError("failed")
    with patch(
        "tablefree.db.ssh_tunnel_manager.SSHTunnelForwarder", return_value=forwarder
    ):
        with pytest.raises(RuntimeError, match="failed"):
            manager.open_tunnel(_profile(), "db.internal", 5432)
