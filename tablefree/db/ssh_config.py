"""SSH tunnel profile configuration types."""

from dataclasses import dataclass
from enum import Enum


class SSHAuthMethod(str, Enum):
    """Supported SSH authentication methods."""

    PASSWORD = "password"
    KEY = "key"


@dataclass(frozen=True)
class SSHProfile:
    """Immutable SSH tunnel configuration."""

    name: str
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = ""
    auth_method: SSHAuthMethod = SSHAuthMethod.KEY
    ssh_password: str = ""
    ssh_key_path: str = ""
    ssh_key_passphrase: str = ""
