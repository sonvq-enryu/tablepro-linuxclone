"""Lifecycle manager for shared SSH tunnels."""

from sshtunnel import SSHTunnelForwarder

from tablefree.db.ssh_config import SSHAuthMethod, SSHProfile


class SSHTunnelManager:
    """Manages active SSH tunnel instances with ref counting."""

    def __init__(self) -> None:
        self._tunnels: dict[str, SSHTunnelForwarder] = {}
        self._ref_counts: dict[str, int] = {}

    def open_tunnel(
        self, profile: SSHProfile, remote_host: str, remote_port: int
    ) -> tuple[str, int]:
        """Open or reuse an SSH tunnel, returning local bind host/port."""
        tunnel_key = self._build_tunnel_key(profile, remote_host, remote_port)
        existing = self._tunnels.get(tunnel_key)
        if existing is not None and existing.is_active:
            self._ref_counts[tunnel_key] = self._ref_counts.get(tunnel_key, 0) + 1
            return "127.0.0.1", int(existing.local_bind_port)

        if existing is not None:
            self._stop_forwarder(existing)
            self._tunnels.pop(tunnel_key, None)
            self._ref_counts.pop(tunnel_key, None)

        kwargs = {
            "ssh_address_or_host": (profile.ssh_host, profile.ssh_port),
            "ssh_username": profile.ssh_user,
            "remote_bind_address": (remote_host, int(remote_port)),
        }
        if profile.auth_method == SSHAuthMethod.PASSWORD:
            kwargs["ssh_password"] = profile.ssh_password
        else:
            kwargs["ssh_pkey"] = profile.ssh_key_path
            if profile.ssh_key_passphrase:
                kwargs["ssh_private_key_password"] = profile.ssh_key_passphrase

        forwarder = SSHTunnelForwarder(**kwargs)
        forwarder.start()
        self._tunnels[tunnel_key] = forwarder
        self._ref_counts[tunnel_key] = 1
        return "127.0.0.1", int(forwarder.local_bind_port)

    def close_tunnel(self, profile: SSHProfile, remote_host: str, remote_port: int) -> None:
        """Decrement ref count and stop tunnel when no longer used."""
        tunnel_key = self._build_tunnel_key(profile, remote_host, remote_port)
        if tunnel_key not in self._tunnels:
            return

        refs = self._ref_counts.get(tunnel_key, 0) - 1
        if refs > 0:
            self._ref_counts[tunnel_key] = refs
            return

        forwarder = self._tunnels.pop(tunnel_key)
        self._ref_counts.pop(tunnel_key, None)
        self._stop_forwarder(forwarder)

    def close_all(self) -> None:
        """Stop and clear all managed tunnels."""
        for forwarder in self._tunnels.values():
            self._stop_forwarder(forwarder)
        self._tunnels.clear()
        self._ref_counts.clear()

    def _build_tunnel_key(
        self, profile: SSHProfile, remote_host: str, remote_port: int
    ) -> str:
        return "|".join(
            [
                profile.ssh_host,
                str(profile.ssh_port),
                profile.ssh_user,
                profile.auth_method.value,
                profile.ssh_key_path,
                remote_host,
                str(remote_port),
            ]
        )

    def _stop_forwarder(self, forwarder: SSHTunnelForwarder) -> None:
        try:
            forwarder.stop()
        except Exception:
            pass
