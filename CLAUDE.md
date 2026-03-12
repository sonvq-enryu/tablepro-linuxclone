# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TableFree is a desktop database management GUI built with Python 3.12, PySide6 (Qt), and uv for dependency management. It supports MySQL and PostgreSQL connections.

## Commands

- **Install dependencies**: `uv sync`
- **Run the app**: `uv run python -m tablefree`
- **Run all tests**: `uv run pytest`
- **Run a single test**: `uv run pytest tests/test_file.py::test_name`

## Architecture

The app follows a three-panel layout: sidebar (connection/schema browser) | editor (SQL query tabs) / result view (query output).

### Key layers

- **`tablefree/app.py`** — QApplication factory, loads resources from `resources/`.
- **`tablefree/main_window.py`** — MainWindow assembles the three-panel layout, menu bar, status bar, and theming (dark/light QSS stylesheets from `resources/styles/`).
- **`tablefree/db/`** — Database abstraction layer:
  - `config.py` — `ConnectionConfig` (frozen dataclass) and `DriverType` enum (POSTGRESQL, MYSQL).
  - `driver.py` — `DatabaseDriver` ABC defining the interface all drivers implement (`connect`, `disconnect`, `execute`, `get_schemas`, `get_tables`, `get_columns`, `get_indexes`). Supports context manager protocol.
  - `mysql_driver.py` / `postgres_driver.py` — Concrete driver implementations using `mysql-connector-python` and `psycopg2-binary`.
  - `manager.py` — `ConnectionManager` registry that maps connection IDs to active `DatabaseDriver` instances. Uses `_DRIVER_MAP` to resolve `DriverType` → driver class.
  - `connection_store.py` — Persists connection profiles via QSettings; stores passwords securely in the system keyring.
- **`tablefree/widgets/`** — Qt widget components: `Sidebar`, `EditorPanel`, `ResultView`, `ConnectionDialog`.
- **`tablefree/workers/`** — `QueryWorker` (QRunnable) runs blocking DB operations off the main thread, emitting `finished`/`error` signals.

### Adding a new database driver

1. Create `tablefree/db/<name>_driver.py` implementing `DatabaseDriver`.
2. Add the driver type to the `DriverType` enum in `config.py`.
3. Register it in `ConnectionManager._DRIVER_MAP`.
