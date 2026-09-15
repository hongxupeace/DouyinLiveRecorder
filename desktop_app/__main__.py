from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from .preferences import AppPreferences
from .repository import RoomRepository
from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DouyinLiveRecorder Desktop")
    app.setOrganizationName("DouyinLiveRecorder")

    application_data = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
    )
    try:
        repository = RoomRepository(application_data / "rooms.db")
        window = MainWindow(repository, AppPreferences())
        window.show()
        return app.exec()
    except Exception as error:  # noqa: BLE001 - GUI startup is the outer error boundary.
        QMessageBox.critical(None, "启动失败", str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
