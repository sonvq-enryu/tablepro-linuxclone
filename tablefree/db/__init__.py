"""tablefree.db — Database driver abstraction layer."""

from tablefree.db.config import ConnectionConfig, DriverType
from tablefree.db.driver import ColumnInfo, DatabaseDriver, IndexInfo
from tablefree.db.manager import ConnectionManager
from tablefree.db.mysql_driver import MySQLDriver
from tablefree.db.postgres_driver import PostgreSQLDriver
from tablefree.db.ssh_config import SSHAuthMethod, SSHProfile
from tablefree.db.ssh_store import SSHProfileStore
from tablefree.db.ssh_tunnel_manager import SSHTunnelManager

__all__ = [
    "ColumnInfo",
    "ConnectionConfig",
    "ConnectionManager",
    "DatabaseDriver",
    "DriverType",
    "IndexInfo",
    "MySQLDriver",
    "PostgreSQLDriver",
    "SSHAuthMethod",
    "SSHProfile",
    "SSHProfileStore",
    "SSHTunnelManager",
]
