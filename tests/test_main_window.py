"""Tests for quick-connect and query-result behavior in MainWindow."""

import time

from PySide6.QtWidgets import QApplication, QMessageBox

from tablefree.main_window import MainWindow
from tablefree.models import QueryResult

APP = QApplication.instance()
if APP is None:
    APP = QApplication(["--platform", "offscreen"])


def test_stale_quick_connect_result_is_ignored_and_closed(monkeypatch) -> None:
    window = MainWindow()
    try:
        closed_ids: list[str] = []
        applied_drivers: list[object] = []

        window._quick_connect_request_id = 2
        monkeypatch.setattr(
            window._conn_manager,
            "close_connection",
            lambda conn_id: closed_ids.append(conn_id),
        )
        monkeypatch.setattr(
            window, "_apply_connected_driver", lambda driver: applied_drivers.append(driver)
        )

        stale_driver = object()
        window._on_sidebar_connect_finished(1, stale_driver, "old-conn")

        assert closed_ids == ["old-conn"]
        assert applied_drivers == []
    finally:
        window.close()


def test_latest_quick_connect_result_is_applied(monkeypatch) -> None:
    window = MainWindow()
    try:
        applied_drivers: list[object] = []
        refreshed = {"count": 0}

        window._quick_connect_request_id = 3
        monkeypatch.setattr(
            window, "_apply_connected_driver", lambda driver: applied_drivers.append(driver)
        )
        monkeypatch.setattr(
            window._sidebar, "refresh_connections", lambda: refreshed.__setitem__("count", 1)
        )

        driver = object()
        window._on_sidebar_connect_finished(3, driver, "new-conn")

        assert window._active_profile_id == "new-conn"
        assert applied_drivers == [driver]
        assert refreshed["count"] == 1
    finally:
        window.close()


def test_stale_quick_connect_error_is_ignored(monkeypatch) -> None:
    window = MainWindow()
    try:
        warnings: list[str] = []

        window._quick_connect_request_id = 5
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *args: warnings.append(str(args[-1]))
        )

        window._on_sidebar_connect_error(4, RuntimeError("stale error"))

        assert warnings == []
    finally:
        window.close()


def test_query_with_no_rows_clears_previous_results_view() -> None:
    window = MainWindow()
    try:
        explain_result = QueryResult(
            columns=["QUERY PLAN"],
            rows=[["Seq Scan on users"]],
            column_types=["text"],
            row_count=1,
            duration_ms=1.2,
            query="EXPLAIN SELECT * FROM users",
        )
        window._result_view.display_results(explain_result)

        window._current_query = "SELECT * FROM users WHERE 1 = 0"
        window._query_start_time = time.perf_counter()
        window._on_query_finished([])

        current = window._result_view.current_result
        assert current is not None
        assert current.query == "SELECT * FROM users WHERE 1 = 0"
        assert current.columns == []
        assert current.rows == []
        assert current.row_count == 0
        assert window._result_view._tabs.currentIndex() == 0
        assert window._editor._info_label.text().startswith("0 rows |")
    finally:
        window.close()


def test_non_result_success_keeps_results_tab_and_clears_stale_rows() -> None:
    window = MainWindow()
    try:
        explain_result = QueryResult(
            columns=["QUERY PLAN"],
            rows=[["Seq Scan on users"]],
            column_types=["text"],
            row_count=1,
            duration_ms=1.2,
            query="EXPLAIN SELECT * FROM users",
        )
        window._result_view.display_results(explain_result)

        window._current_query = "UPDATE users SET active = true"
        window._query_start_time = time.perf_counter()
        window._on_query_finished((3, None))

        current = window._result_view.current_result
        assert current is not None
        assert current.query == "UPDATE users SET active = true"
        assert current.columns == []
        assert current.rows == []
        assert current.row_count == 0
        assert window._result_view._tabs.currentIndex() == 0
        assert window._editor._info_label.text().startswith("3 rows |")
    finally:
        window.close()
