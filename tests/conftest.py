"""Shared test fixtures for database driver tests."""

import os

import pytest

from tablefree.db.config import ConnectionConfig, DriverType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def pg_config():
    """PostgreSQL connection config for local testing."""
    return ConnectionConfig(
        host="localhost",
        port=5432,
        database="tablefree_test",
        username="postgres",
        password="postgres",
        driver_type=DriverType.POSTGRESQL,
        name="test-pg",
    )


@pytest.fixture
def mysql_config():
    """MySQL connection config for local testing."""
    return ConnectionConfig(
        host="localhost",
        port=3306,
        database="tablefree_test",
        username="root",
        password="root",
        driver_type=DriverType.MYSQL,
        name="test-mysql",
    )
