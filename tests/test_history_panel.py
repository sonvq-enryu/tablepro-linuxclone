"""Tests for tablefree.widgets.history_panel."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from tablefree.services import QueryHistoryStore
from tablefree.widgets.history_panel import HistoryPanel

APP = QApplication.instance()
if APP is None:
    APP = QApplication(["--platform", "offscreen"])


def _panel(tmp_path: Path) -> tuple[QueryHistoryStore, HistoryPanel]:
    store = QueryHistoryStore(db_path=str(tmp_path / "history.db"))
    panel = HistoryPanel(store=store)
    return store, panel


def test_double_click_emits_load_signal(tmp_path: Path) -> None:
    store, panel = _panel(tmp_path)
    store.record("SELECT * FROM users", "conn", 4.2, "success")
    panel.refresh(reset=True)

    captured: list[str] = []
    panel.query_load_requested.connect(captured.append)
    panel._on_table_double_clicked(0, 0)

    assert captured == ["SELECT * FROM users"]


def test_run_signal_path_and_delete_entry(tmp_path: Path) -> None:
    store, panel = _panel(tmp_path)
    entry_id = store.record("SELECT 42", "conn", 1.0, "success")
    panel.refresh(reset=True)

    captured: list[str] = []
    panel.query_run_requested.connect(captured.append)
    panel._emit_run("SELECT 42")
    assert captured == ["SELECT 42"]

    panel._delete_entry(entry_id)
    assert store.get_entry(entry_id) is None


def test_clear_button_clears_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, panel = _panel(tmp_path)
    store.record("SELECT * FROM users", "conn", 1.0, "success")
    store.record("SELECT * FROM orders", "conn", 1.0, "success")
    panel.refresh(reset=True)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    panel._on_clear_clicked()

    assert store.search(limit=100) == []
