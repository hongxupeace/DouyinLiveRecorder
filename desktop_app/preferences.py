from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from .domain import ProbeSettings


class AppPreferences:
    def __init__(self):
        self._settings = QSettings("DouyinLiveRecorder", "Desktop")

    @property
    def output_directory(self) -> str:
        default_root = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
        )
        default_value = str(Path(default_root) / "DouyinLiveRecorder")
        return str(self._settings.value("recording/output_directory", default_value))

    @output_directory.setter
    def output_directory(self, value: str) -> None:
        self._settings.setValue("recording/output_directory", value)

    @property
    def douyin_cookie(self) -> str:
        return str(self._settings.value("network/douyin_cookie", ""))

    @douyin_cookie.setter
    def douyin_cookie(self, value: str) -> None:
        self._settings.setValue("network/douyin_cookie", value)

    @property
    def proxy(self) -> str:
        return str(self._settings.value("network/proxy", ""))

    @proxy.setter
    def proxy(self, value: str) -> None:
        self._settings.setValue("network/proxy", value)

    @property
    def monitor_interval(self) -> int:
        return max(10, int(self._settings.value("monitor/interval_seconds", 60)))

    @monitor_interval.setter
    def monitor_interval(self, value: int) -> None:
        self._settings.setValue("monitor/interval_seconds", max(10, value))

    def probe_settings(self) -> ProbeSettings:
        return ProbeSettings(
            cookie=self.douyin_cookie,
            proxy=self.proxy,
        )
