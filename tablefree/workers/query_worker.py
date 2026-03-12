"""Background worker for blocking database operations."""

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class _WorkerSignals(QObject):
    """Defines the signals available from a running worker thread.

    QRunnable itself cannot emit signals, so we use a nested QObject.
    """

    finished = Signal(object)
    error = Signal(Exception)


class QueryWorker(QRunnable):
    """Runnable worker for executing blocking functions on a background thread.

    This worker is used to prevent blocking the Qt main event loop when
    establishing database connections or running long queries.

    Args:
        fn: A callable to execute in the background.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self) -> None:
        """Execute the function and emit the appropriate signal."""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(e)
