"""TableFree — Entry point."""

import sys

from tablefree.app import create_app
from tablefree.main_window import MainWindow


def main() -> None:
    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
