"""Tests for editor tab persistence and tab UX behaviors."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tablefree.widgets.editor import EditorPanel


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )


def _editor_sqls(panel: EditorPanel) -> list[str]:
    sqls = []
    for i in range(panel._tabs.count()):
        editor = panel._tabs.widget(i)
        sqls.append(editor.toPlainText())
    return sqls


def test_tab_persistence_roundtrip(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-a")
    panel.current_editor().setPlainText("SELECT 1;")
    panel._new_tab()
    panel.current_editor().setPlainText("SELECT 2;")
    panel._new_tab()
    panel.current_editor().setPlainText("SELECT 3;")
    panel.save_tab_states()

    restored = EditorPanel()
    restored.restore_tabs("conn-a")
    assert restored._tabs.count() == 3
    assert _editor_sqls(restored) == ["SELECT 1;", "SELECT 2;", "SELECT 3;"]


def test_persistence_is_scoped_by_connection(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-a")
    panel.current_editor().setPlainText("SELECT 'A';")
    panel.save_tab_states()

    panel.restore_tabs("conn-b")
    panel.current_editor().setPlainText("SELECT 'B';")
    panel.save_tab_states()

    a = EditorPanel()
    a.restore_tabs("conn-a")
    b = EditorPanel()
    b.restore_tabs("conn-b")
    assert _editor_sqls(a) == ["SELECT 'A';"]
    assert _editor_sqls(b) == ["SELECT 'B';"]


def test_pinned_tab_refuses_close(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-pin")
    assert panel._tabs.count() == 1
    panel._toggle_pin(0)
    panel._close_tab(0)
    assert panel._tabs.count() == 1


def test_close_others_keeps_pinned_and_current(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-close-others")
    panel.current_editor().setPlainText("keep pinned")
    panel._toggle_pin(0)

    panel._new_tab()
    panel.current_editor().setPlainText("keep current")
    keep_index = panel._tabs.currentIndex()

    panel._new_tab()
    panel.current_editor().setPlainText("close me")

    panel._close_other_tabs(keep_index)
    assert panel._tabs.count() == 2
    assert _editor_sqls(panel) == ["keep pinned", "keep current"]


def test_reopen_closed_tab_restores_sql(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-reopen")
    panel._new_tab()
    panel.current_editor().setPlainText("SELECT reopened;")
    panel._close_current_tab()
    panel._reopen_last_closed_tab()
    assert panel.current_editor().toPlainText() == "SELECT reopened;"


def test_autosave_debounce_persists_text(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-autosave")
    panel.current_editor().setPlainText("SELECT debounce;")
    QTest.qWait(650)

    settings = QSettings()
    payload = settings.value("tabs/conn-autosave", "")
    assert isinstance(payload, str)
    assert "SELECT debounce;" in payload


def test_context_menu_labels_reflect_pin_state(qapp, isolated_settings):
    panel = EditorPanel()
    panel.restore_tabs("conn-menu")
    assert panel._context_menu_labels_for_index(0)[3] == "Pin Tab"
    panel._toggle_pin(0)
    assert panel._context_menu_labels_for_index(0)[3] == "Unpin Tab"
