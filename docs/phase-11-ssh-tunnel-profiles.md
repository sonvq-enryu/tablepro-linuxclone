# Phase 11: SSH Tunnel Profiles

## Goal

Allow users to create reusable SSH tunnel profiles (bastion hosts) that can be shared across multiple database connections. A single bastion profile is defined once and referenced by any number of connections, eliminating repetitive SSH configuration. The SSH tunnel is established transparently before the database driver connects, routing traffic through the bastion.

## Current State

- `ConnectionDialog` already collects SSH fields (`ssh_enabled`, `ssh_host`, `ssh_port`, `ssh_user`, `ssh_key`) in the Advanced Options section — but they are stored inline per-connection and never used
- `ConnectionConfig` has no SSH-related fields; `ConnectionStore.to_config()` silently drops all `ssh_*` keys
- Neither `PostgreSQLDriver` nor `MySQLDriver` handles SSH tunneling
- `ConnectionManager.create_connection()` calls `driver.connect()` directly with no tunnel setup

## New Dependency

Add `sshtunnel` (wraps paramiko) to `pyproject.toml`:

```toml
dependencies = [
    ...
    "sshtunnel>=0.4.0",
]
```

---

## Task 1: SSH Profile Data Model

### New file: `tablefree/db/ssh_config.py`

Define the SSH authentication method enum and the frozen dataclass for SSH profile configuration:

```python
from dataclasses import dataclass
from enum import Enum


class SSHAuthMethod(str, Enum):
    PASSWORD = "password"
    KEY = "key"


@dataclass(frozen=True)
class SSHProfile:
    """Immutable SSH tunnel configuration.

    Attributes:
        name: Human-friendly label (e.g. "Production Bastion").
        ssh_host: Bastion server hostname or IP.
        ssh_port: SSH port on the bastion (default 22).
        ssh_user: SSH username.
        auth_method: PASSWORD or KEY.
        ssh_password: Password for password auth (empty string if unused).
        ssh_key_path: Absolute path to private key file (empty string if unused).
        ssh_key_passphrase: Passphrase for encrypted key (empty string if unused).
    """
    name: str
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = ""
    auth_method: SSHAuthMethod = SSHAuthMethod.KEY
    ssh_password: str = ""
    ssh_key_path: str = ""
    ssh_key_passphrase: str = ""
```

This mirrors the existing `ConnectionConfig` pattern — a frozen dataclass that is constructed once and passed around immutably.

---

## Task 2: SSH Profile Store

### New file: `tablefree/db/ssh_store.py`

Persist SSH profiles using QSettings (group `"ssh_profiles"`) + keyring for secrets. Follows the exact same pattern as `ConnectionStore`.

```python
class SSHProfileStore:
    SERVICE_NAME = "TableFree-SSH"
    _GROUP = "ssh_profiles"

    def save(self, profile: dict, profile_id: str | None = None) -> str:
        """Save profile metadata to QSettings, secrets to keyring."""

    def load_all(self) -> list[dict]:
        """Load all SSH profiles, sorted by name."""

    def load(self, profile_id: str) -> dict | None:
        """Load a single SSH profile by ID."""

    def delete(self, profile_id: str) -> None:
        """Delete a profile from QSettings and keyring."""

    def to_ssh_profile(self, data: dict) -> SSHProfile:
        """Convert a profile dict to an SSHProfile dataclass."""
```

**Keyring keys:** Store up to 2 secrets per profile:
- `keyring.set_password("TableFree-SSH", f"{profile_id}:password", ...)` for SSH password
- `keyring.set_password("TableFree-SSH", f"{profile_id}:passphrase", ...)` for key passphrase

**QSettings data (JSON):** `name`, `ssh_host`, `ssh_port`, `ssh_user`, `auth_method`, `ssh_key_path` — no secrets in QSettings.

---

## Task 3: SSH Tunnel Manager

### New file: `tablefree/db/ssh_tunnel_manager.py`

Manages the lifecycle of `SSHTunnelForwarder` instances. Each active tunnel is keyed by `(ssh_profile_id, remote_host, remote_port)` so that two connections going through the same bastion to the same target can share one tunnel, but connections to different targets get separate tunnels.

```python
from sshtunnel import SSHTunnelForwarder
from tablefree.db.ssh_config import SSHProfile, SSHAuthMethod


class SSHTunnelManager:
    """Manages active SSH tunnel instances."""

    def __init__(self) -> None:
        self._tunnels: dict[str, SSHTunnelForwarder] = {}  # tunnel_key -> forwarder
        self._ref_counts: dict[str, int] = {}              # tunnel_key -> usage count

    def open_tunnel(
        self, profile: SSHProfile, remote_host: str, remote_port: int
    ) -> tuple[str, int]:
        """Open (or reuse) an SSH tunnel. Returns (local_host, local_port).

        Steps:
        1. Build tunnel_key from profile + remote target.
        2. If tunnel already exists and is alive, increment ref count, return its local bind.
        3. Otherwise, create SSHTunnelForwarder:
           - ssh_address_or_host=(profile.ssh_host, profile.ssh_port)
           - ssh_username=profile.ssh_user
           - ssh_password or ssh_pkey depending on profile.auth_method
           - remote_bind_address=(remote_host, remote_port)
        4. Call forwarder.start(), store it, return ('127.0.0.1', forwarder.local_bind_port).
        """

    def close_tunnel(self, profile: SSHProfile, remote_host: str, remote_port: int) -> None:
        """Decrement ref count; stop the tunnel when count reaches 0."""

    def close_all(self) -> None:
        """Stop all tunnels."""
```

**Key behaviors:**
- `open_tunnel()` is called in the worker thread (before `driver.connect()`) — blocking is fine
- `close_tunnel()` is called after `driver.disconnect()`
- Ref counting allows multiple connections through the same bastion+target to share a tunnel
- If `SSHTunnelForwarder.start()` fails, raise immediately so the caller gets a clear error

---

## Task 4: Wire Tunnel into ConnectionManager

### Modify: `tablefree/db/manager.py`

`ConnectionManager` currently does: instantiate driver -> `driver.connect()`. With SSH, the flow becomes: open tunnel -> override host/port -> instantiate driver -> `driver.connect()`.

**Changes:**

1. Add `SSHTunnelManager` as a member (`self._tunnel_manager`).
2. Add `SSHProfileStore` as a member (`self._ssh_store`).
3. Extend `create_connection()` to accept an optional `ssh_profile_id: str | None`:

```python
def create_connection(
    self, connection_id: str, config: ConnectionConfig, ssh_profile_id: str | None = None
) -> DatabaseDriver:
    if connection_id in self._connections:
        raise ValueError(f"Connection '{connection_id}' already exists")

    effective_config = config

    if ssh_profile_id:
        ssh_data = self._ssh_store.load(ssh_profile_id)
        if ssh_data is None:
            raise ValueError(f"SSH profile '{ssh_profile_id}' not found")
        ssh_profile = self._ssh_store.to_ssh_profile(ssh_data)

        local_host, local_port = self._tunnel_manager.open_tunnel(
            ssh_profile, config.host, config.port
        )
        # Replace host/port with tunnel's local bind
        effective_config = ConnectionConfig(
            host=local_host,
            port=local_port,
            database=config.database,
            username=config.username,
            password=config.password,
            driver_type=config.driver_type,
            name=config.name,
            ssl=config.ssl,
            options=config.options,
        )
        self._tunnel_map[connection_id] = (ssh_profile, config.host, config.port)

    driver_cls = self._DRIVER_MAP.get(effective_config.driver_type)
    if driver_cls is None:
        raise ValueError(f"Unsupported driver type: {effective_config.driver_type}")

    driver = driver_cls(effective_config)
    driver.connect()
    self._connections[connection_id] = driver
    return driver
```

4. Extend `close_connection()` to close the tunnel after disconnecting the driver:

```python
def close_connection(self, connection_id: str) -> None:
    driver = self._connections.pop(connection_id, None)
    if driver is not None:
        driver.disconnect()

    tunnel_info = self._tunnel_map.pop(connection_id, None)
    if tunnel_info:
        ssh_profile, remote_host, remote_port = tunnel_info
        self._tunnel_manager.close_tunnel(ssh_profile, remote_host, remote_port)
```

5. Extend `close_all()` to call `self._tunnel_manager.close_all()` after closing all drivers.

---

## Task 5: Wire Tunnel into ConnectionStore

### Modify: `tablefree/db/connection_store.py`

Currently, the connection profile dict stores `ssh_enabled`, `ssh_host`, `ssh_port`, `ssh_user`, `ssh_key` inline. Replace these with a single `ssh_profile_id` reference.

**Changes to `save()`:**
- Before saving to QSettings, strip out the old inline SSH fields if present (`ssh_enabled`, `ssh_host`, `ssh_port`, `ssh_user`, `ssh_key`)
- Preserve the new `ssh_profile_id` field (string or empty) in the JSON payload

**Changes to `to_config()`:**
- No changes needed — `to_config()` already ignores unknown keys and only builds `ConnectionConfig` from DB fields
- The `ssh_profile_id` is consumed separately by `ConnectionManager`

**Data migration:**
- No automatic migration needed; old profiles with inline SSH fields simply won't have `ssh_profile_id`
- The inline fields remain in storage but are ignored; they can be cleaned up in a future release

---

## Task 6: SSH Profile Management Dialog

### New file: `tablefree/widgets/ssh_profile_dialog.py`

A standalone `QDialog` for CRUD operations on SSH profiles. Accessible from the Connection Dialog.

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  SSH Profiles                                           │
├──────────────────┬──────────────────────────────────────┤
│ [Search...]      │  Profile Name: [Production Bastion]  │
│                  │                                       │
│ > Prod Bastion   │  SSH Host: [bastion.example.com]     │
│   Staging Jump   │  SSH Port: [22]                      │
│                  │  SSH User: [deploy]                  │
│                  │                                       │
│                  │  Auth Method: (o) Key  ( ) Password  │
│                  │                                       │
│                  │  Key Path: [~/.ssh/id_rsa] [Browse]  │
│                  │  Passphrase: [••••••••]              │
│                  │                                       │
│ [+ New Profile]  │        [Delete] [Cancel] [Save]      │
└──────────────────┴──────────────────────────────────────┘
```

**Two-panel layout (mirrors ConnectionDialog pattern):**
- Left panel: search + list of saved SSH profiles + "New Profile" button
- Right panel: form for editing the selected profile

**Form fields:**
- Profile Name (`QLineEdit`)
- SSH Host (`QLineEdit`)
- SSH Port (`QSpinBox`, range 1-65535, default 22)
- SSH User (`QLineEdit`)
- Auth Method (`QRadioButton` group: Key / Password)
- Key Path (`QLineEdit` + Browse `QPushButton`) — visible when auth=KEY
- Key Passphrase (`QLineEdit`, password echo mode) — visible when auth=KEY
- SSH Password (`QLineEdit`, password echo mode) — visible when auth=PASSWORD

**Actions:**
- **Save:** validate required fields, call `SSHProfileStore.save()`
- **Delete:** confirm dialog, call `SSHProfileStore.delete()`
- **Cancel:** close dialog
- **Test Tunnel:** open an SSH connection only (no DB), verify it succeeds. Use `SSHTunnelForwarder` with a dummy `remote_bind_address=('127.0.0.1', 22)` and check that `start()` succeeds, then `stop()`.

**Signals:**
- `profile_saved(str)` — emits profile_id when a save completes (so ConnectionDialog can refresh its dropdown)

---

## Task 7: Update Connection Dialog

### Modify: `tablefree/widgets/connection_dialog.py`

Replace the inline SSH fields with a profile selection dropdown.

**Replace the SSH section in Advanced Options:**

Remove the old SSH fields container (`_ssh_fields_container` with `ssh_host`, `ssh_port`, `ssh_user`, `ssh_key` inputs).

Add new SSH section:

```
SSH Tunnel
Route database traffic through a secure bastion host.

[✓] Use SSH Tunnel

SSH Profile: [ Production Bastion  ▼ ]  [ Manage Profiles... ]

   Host: bastion.example.com          (read-only summary)
   User: deploy
   Auth: Key (~/.ssh/id_rsa)
```

**New widgets:**
- `_ssh_checkbox` (keep existing)
- `_ssh_profile_combo` — `QComboBox` populated from `SSHProfileStore.load_all()`. Item data = `profile_id`. First item: "Select SSH profile..." (disabled placeholder).
- `_ssh_manage_btn` — `QPushButton("Manage Profiles...")` that opens `SSHProfileDialog`
- `_ssh_summary_widget` — read-only `QWidget` showing host/user/auth of the selected profile (appears below the combo when a profile is selected)

**Behavior:**
- When `_ssh_checkbox` is toggled ON, show the combo + manage button
- When a profile is selected in the combo, show the summary below it
- "Manage Profiles..." opens `SSHProfileDialog`; on `profile_saved` signal, refresh the combo
- When `_ssh_checkbox` is OFF, the combo and summary are hidden

**Changes to `_get_form_profile()`:**

Replace old SSH fields:
```python
def _get_form_profile(self) -> dict[str, Any]:
    return {
        ...
        "ssh_profile_id": self._get_selected_ssh_profile_id(),
        # Remove: ssh_enabled, ssh_host, ssh_port, ssh_user, ssh_key
    }
```

Where `_get_selected_ssh_profile_id()` returns the profile_id from the combo's current item data, or empty string if none selected / SSH disabled.

**Changes to `_set_form_profile()`:**

Set the combo to match `profile.get("ssh_profile_id", "")`:
```python
self._ssh_checkbox.setChecked(bool(profile.get("ssh_profile_id")))
self._select_ssh_profile_in_combo(profile.get("ssh_profile_id", ""))
```

**Changes to `_connect_with_profile()`:**

Pass `ssh_profile_id` through to `ConnectionManager.create_connection()`:
```python
worker = QueryWorker(
    self._manager.create_connection,
    self._current_conn_id,
    config,
    profile.get("ssh_profile_id") or None,
)
```

**Changes to `_on_test_clicked()`:**

Test must also set up a tunnel if SSH is enabled. Create a temporary `SSHTunnelForwarder`, open it, override config host/port, then test the driver, then stop the tunnel. All within the worker thread.

---

## Task 8: Styling

### Modify: `resources/styles/dark.qss` and `resources/styles/light.qss`

Add styles for new SSH Profile Dialog and updated Connection Dialog widgets:
- `#ssh-profile-dialog` — dialog dimensions and background
- `#ssh-profile-list` — list widget in left panel
- `#ssh-profile-form` — form widget in right panel
- `#ssh-profile-combo` — combo box in connection dialog SSH section
- `#ssh-summary-widget` — read-only summary card
- `#ssh-manage-btn` — "Manage Profiles" button
- `#auth-method-group` — radio button group styling

Follow the existing QSS patterns used for `#connection-dialog`, `#connection-list-panel`, `#connection-form-panel`, etc.

---

## Task 9: Tests

### New file: `tests/test_ssh_store.py`

Mirrors `tests/test_connection_store.py` structure:
- `test_save_and_load_profile` — save a profile, load it back, verify all fields match
- `test_load_all_sorted_by_name` — save 3 profiles, load_all returns them alphabetically
- `test_delete_profile` — save then delete, verify load returns None
- `test_to_ssh_profile_key_auth` — convert dict with auth_method=KEY, verify SSHProfile fields
- `test_to_ssh_profile_password_auth` — convert dict with auth_method=PASSWORD
- `test_secrets_stored_in_keyring` — verify password and passphrase go to keyring, not QSettings

### New file: `tests/test_ssh_tunnel_manager.py`

- `test_open_tunnel_returns_local_bind` — mock `SSHTunnelForwarder`, verify `open_tunnel()` returns `('127.0.0.1', <port>)` and calls `forwarder.start()`
- `test_open_tunnel_reuses_existing` — open same tunnel twice, verify `SSHTunnelForwarder` is only created once, ref count is 2
- `test_close_tunnel_decrements_ref` — open twice, close once, verify tunnel still alive
- `test_close_tunnel_stops_at_zero_refs` — open once, close once, verify `forwarder.stop()` called
- `test_close_all` — open 3 tunnels, close_all, verify all stopped
- `test_open_tunnel_failure_raises` — mock `forwarder.start()` to raise, verify exception propagates

### Extend: `tests/test_connection_store.py`

- `test_save_with_ssh_profile_id` — save a profile with `ssh_profile_id`, load it back, verify the field persists
- `test_to_config_ignores_ssh_profile_id` — verify `to_config()` still works with `ssh_profile_id` in the dict

---

## Data Flow

```
User clicks "Save & Connect" in ConnectionDialog
  → _on_connect_clicked()
    → profile = _get_form_profile()  # includes ssh_profile_id
    → ConnectionStore.save(profile)
    → ConnectionStore.to_config(profile)  # builds ConnectionConfig (DB fields only)
    → QueryWorker(ConnectionManager.create_connection, conn_id, config, ssh_profile_id)
      → [worker thread]
      → if ssh_profile_id:
          → SSHProfileStore.load(ssh_profile_id)
          → SSHTunnelManager.open_tunnel(ssh_profile, config.host, config.port)
          → returns ('127.0.0.1', local_port)
          → build effective_config with host='127.0.0.1', port=local_port
      → driver = DriverClass(effective_config)
      → driver.connect()  # connects through tunnel
      → return driver
  → _on_connect_finished(driver)
    → self._active_driver = driver
    → dialog.accept()
```

## File Summary

| File | Action |
|---|---|
| `pyproject.toml` | Add `sshtunnel>=0.4.0` dependency |
| `tablefree/db/ssh_config.py` | **New** — `SSHAuthMethod` enum, `SSHProfile` frozen dataclass |
| `tablefree/db/ssh_store.py` | **New** — `SSHProfileStore` (QSettings + keyring persistence) |
| `tablefree/db/ssh_tunnel_manager.py` | **New** — `SSHTunnelManager` (tunnel lifecycle + ref counting) |
| `tablefree/db/manager.py` | **Modify** — accept `ssh_profile_id`, open/close tunnels around driver |
| `tablefree/db/connection_store.py` | **Modify** — strip old inline SSH fields, preserve `ssh_profile_id` |
| `tablefree/widgets/ssh_profile_dialog.py` | **New** — SSH profile CRUD dialog |
| `tablefree/widgets/connection_dialog.py` | **Modify** — replace inline SSH fields with profile combo + manage button |
| `resources/styles/dark.qss` | **Modify** — add SSH profile widget styles |
| `resources/styles/light.qss` | **Modify** — add SSH profile widget styles |
| `tests/test_ssh_store.py` | **New** — SSHProfileStore tests |
| `tests/test_ssh_tunnel_manager.py` | **New** — SSHTunnelManager tests |
| `tests/test_connection_store.py` | **Modify** — add ssh_profile_id round-trip tests |

## Dependencies

- `sshtunnel>=0.4.0` (PyPI, wraps paramiko)
- Existing: `PySide6`, `keyring`, `psycopg2-binary`, `mysql-connector-python`
