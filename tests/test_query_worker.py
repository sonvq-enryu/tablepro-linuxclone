"""Unit tests for QueryWorker."""

from PySide6.QtCore import QEventLoop, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

APP = QApplication.instance()
if APP is None:
    APP = QApplication(["--platform", "offscreen"])

from tablefree.workers import QueryWorker


def test_worker_emits_finished() -> None:
    pool = QThreadPool.globalInstance()
    loop = QEventLoop()

    result_val = None

    def my_func(a: int, b: int) -> int:
        return a + b

    def on_finished(res: int) -> None:
        nonlocal result_val
        result_val = res
        loop.quit()

    worker = QueryWorker(my_func, 2, 3)
    worker.signals.finished.connect(on_finished)
    worker.signals.error.connect(loop.quit)

    pool.start(worker)
    
    # Timeout after 1 second if signal not emitted
    QTimer.singleShot(1000, loop.quit)
    loop.exec()

    assert result_val == 5


def test_worker_emits_error() -> None:
    pool = QThreadPool.globalInstance()
    loop = QEventLoop()

    error_val = None

    def my_bad_func() -> None:
        raise ValueError("Oh no")

    def on_error(err: Exception) -> None:
        nonlocal error_val
        error_val = err
        loop.quit()

    worker = QueryWorker(my_bad_func)
    worker.signals.error.connect(on_error)
    worker.signals.finished.connect(loop.quit)

    pool.start(worker)
    
    QTimer.singleShot(1000, loop.quit)
    loop.exec()

    assert isinstance(error_val, ValueError)
    assert str(error_val) == "Oh no"
