"""ConnectionManager — central registry for active database connections."""

from dataclasses import replace

from tablefree.db.config import ConnectionConfig, DriverType
from tablefree.db.driver import DatabaseDriver
from tablefree.db.mysql_driver import MySQLDriver
from tablefree.db.postgres_driver import PostgreSQLDriver
from tablefree.db.ssh_config import SSHProfile
from tablefree.db.ssh_store import SSHProfileStore
from tablefree.db.ssh_tunnel_manager import SSHTunnelManager


class ConnectionManager:
    """Manages active database connections.

    Each connection is identified by a unique string *connection_id*.
    The manager maps driver types to concrete driver classes and handles
    the full lifecycle: create → use → close.
    """

    _DRIVER_MAP: dict[DriverType, type[DatabaseDriver]] = {
        DriverType.POSTGRESQL: PostgreSQLDriver,
        DriverType.MYSQL: MySQLDriver,
    }

    def __init__(self) -> None:
        self._connections: dict[str, DatabaseDriver] = {}
        self._tunnel_manager = SSHTunnelManager()
        self._ssh_store = SSHProfileStore()
        self._tunnel_map: dict[str, tuple[SSHProfile, str, int]] = {}

    # ── Public API ───────────────────────────────────────────

    def create_connection(
        self,
        connection_id: str,
        config: ConnectionConfig,
        ssh_profile_id: str | None = None,
    ) -> DatabaseDriver:
        """Create, connect, and register a new driver instance.

        Raises:
            ValueError: If *connection_id* is already in use or the
                driver type is not supported.
        """
        if connection_id in self._connections:
            raise ValueError(f"Connection '{connection_id}' already exists")

        effective_config = config
        tunnel_info: tuple[SSHProfile, str, int] | None = None

        if ssh_profile_id:
            ssh_data = self._ssh_store.load(ssh_profile_id)
            if ssh_data is None:
                raise ValueError(f"SSH profile '{ssh_profile_id}' not found")
            ssh_profile = self._ssh_store.to_ssh_profile(ssh_data)
            local_host, local_port = self._tunnel_manager.open_tunnel(
                ssh_profile, config.host, config.port
            )
            effective_config = replace(config, host=local_host, port=local_port)
            tunnel_info = (ssh_profile, config.host, config.port)

        driver_cls = self._DRIVER_MAP.get(effective_config.driver_type)
        if driver_cls is None:
            if tunnel_info is not None:
                self._tunnel_manager.close_tunnel(*tunnel_info)
            raise ValueError(f"Unsupported driver type: {effective_config.driver_type}")

        driver = driver_cls(effective_config)
        try:
            driver.connect()
        except Exception:
            if tunnel_info is not None:
                self._tunnel_manager.close_tunnel(*tunnel_info)
            raise
        self._connections[connection_id] = driver
        if tunnel_info is not None:
            self._tunnel_map[connection_id] = tunnel_info
        return driver

    def get_connection(self, connection_id: str) -> DatabaseDriver:
        """Retrieve an active driver by its *connection_id*.

        Raises:
            KeyError: If no connection exists with that ID.
        """
        if connection_id not in self._connections:
            raise KeyError(f"No connection with ID '{connection_id}'")
        return self._connections[connection_id]

    def close_connection(self, connection_id: str) -> None:
        """Disconnect and remove a connection by its *connection_id*."""
        driver = self._connections.pop(connection_id, None)
        try:
            if driver is not None:
                driver.disconnect()
        finally:
            tunnel_info = self._tunnel_map.pop(connection_id, None)
            if tunnel_info is not None:
                self._tunnel_manager.close_tunnel(*tunnel_info)

    def close_all(self) -> None:
        """Disconnect every active connection."""
        for conn_id in list(self._connections):
            self.close_connection(conn_id)
        self._tunnel_manager.close_all()

    # ── Properties ───────────────────────────────────────────

    @property
    def active_connections(self) -> dict[str, DatabaseDriver]:
        """Return a shallow copy of the active connections dict."""
        return dict(self._connections)
