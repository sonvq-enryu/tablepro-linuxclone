"""Tests for quick-connect behavior in MainWindow."""

from PySide6.QtWidgets import QApplication, QMessageBox

from tablefree.main_window import MainWindow

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
