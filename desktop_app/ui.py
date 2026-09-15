from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCloseEvent, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .domain import LiveStatus, ProbeResult, RecordingStatus, Room
from .monitoring import MonitoringCoordinator
from .preferences import AppPreferences
from .recording import RecordingManager
from .repository import DuplicateRoomError, RoomRepository

LIVE_STATUS_TEXT = {
    LiveStatus.UNKNOWN: "未知",
    LiveStatus.CHECKING: "检测中",
    LiveStatus.LIVE: "直播中",
    LiveStatus.OFFLINE: "未开播",
    LiveStatus.ERROR: "检测失败",
}

RECORDING_STATUS_TEXT = {
    RecordingStatus.IDLE: "未录制",
    RecordingStatus.STARTING: "启动中",
    RecordingStatus.RECORDING: "录制中",
    RecordingStatus.STOPPING: "停止中",
    RecordingStatus.FAILED: "录制失败",
}


class AddRoomDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("添加监控直播间")
        self.setMinimumWidth(520)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("可留空，将根据地址生成")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("抖音直播间或 m3u8/flv 地址")
        self.monitor_checkbox = QCheckBox("添加后立即开启监控")
        self.monitor_checkbox.setChecked(True)

        form = QFormLayout()
        form.addRow("名称", self.name_edit)
        form.addRow("直播间地址", self.url_edit)
        form.addRow("", self.monitor_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def room(self) -> Room:
        return Room.create(
            name=self.name_edit.text(),
            url=self.url_edit.text(),
            monitor_enabled=self.monitor_checkbox.isChecked(),
        )

    def _validate_and_accept(self) -> None:
        try:
            self.room()
        except ValueError as error:
            QMessageBox.warning(self, "地址无效", str(error))
            return
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, preferences: AppPreferences, parent: QWidget | None = None):
        super().__init__(parent)
        self.preferences = preferences
        self.setWindowTitle("应用设置")
        self.setMinimumWidth(620)

        self.output_edit = QLineEdit(preferences.output_directory)
        browse_button = QPushButton("选择…")
        browse_button.clicked.connect(self._select_output_directory)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(browse_button)

        self.cookie_edit = QPlainTextEdit(preferences.douyin_cookie)
        self.cookie_edit.setPlaceholderText("可选；遇到抖音风控时填写浏览器 Cookie")
        self.cookie_edit.setMaximumHeight(100)
        self.proxy_edit = QLineEdit(preferences.proxy)
        self.proxy_edit.setPlaceholderText("例如 http://127.0.0.1:7890，可留空")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 3600)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(preferences.monitor_interval)

        form = QFormLayout()
        form.addRow("录制保存目录", output_layout)
        form.addRow("监控间隔", self.interval_spin)
        form.addRow("代理地址", self.proxy_edit)
        form.addRow("抖音 Cookie", self.cookie_edit)

        security_tip = QLabel(
            "Cookie 只保存在当前 Windows 用户的应用设置中，不会写入项目配置文件。"
        )
        security_tip.setWordWrap(True)
        security_tip.setStyleSheet("color: palette(mid);")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(security_tip)
        layout.addWidget(buttons)

    def _select_output_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择录制保存目录",
            self.output_edit.text(),
        )
        if selected:
            self.output_edit.setText(selected)

    def _save(self) -> None:
        output_directory = self.output_edit.text().strip()
        if not output_directory:
            QMessageBox.warning(self, "设置无效", "录制保存目录不能为空")
            return
        self.preferences.output_directory = output_directory
        self.preferences.monitor_interval = self.interval_spin.value()
        self.preferences.proxy = self.proxy_edit.text().strip()
        self.preferences.douyin_cookie = self.cookie_edit.toPlainText().strip()
        self.accept()


class MainWindow(QMainWindow):
    def __init__(
        self,
        repository: RoomRepository,
        preferences: AppPreferences,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.preferences = preferences
        self.rooms = {room.id: room for room in repository.list_rooms()}
        self._closed = False

        self.recording_manager = RecordingManager(self)
        self.monitoring = MonitoringCoordinator(
            room_provider=lambda: list(self.rooms.values()),
            settings_provider=self.preferences.probe_settings,
            interval_provider=lambda: self.preferences.monitor_interval,
            parent=self,
        )

        self.setWindowTitle("直播监控录制")
        self.resize(1180, 720)
        self._build_ui()
        self._connect_signals()
        self._refresh_table()
        self.monitoring.start()

    def _build_ui(self) -> None:
        add_button = QPushButton("添加直播间")
        add_button.clicked.connect(self._add_room)
        refresh_button = QPushButton("刷新状态")
        refresh_button.clicked.connect(self._refresh_all)
        settings_button = QPushButton("设置")
        settings_button.clicked.connect(self._open_settings)
        output_button = QPushButton("打开录制目录")
        output_button.clicked.connect(self._open_output_directory)

        toolbar = QHBoxLayout()
        toolbar.addWidget(add_button)
        toolbar.addWidget(refresh_button)
        toolbar.addStretch()
        toolbar.addWidget(output_button)
        toolbar.addWidget(settings_button)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: 600; padding: 4px 0;")

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "名称",
                "直播间地址",
                "平台",
                "直播状态",
                "录制状态",
                "上次检测",
                "监控",
                "录制",
                "操作",
            ]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 150)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("检测和录制日志会显示在这里")
        self.log_view.document().setMaximumBlockCount(500)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.log_view)
        splitter.setSizes([520, 140])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addLayout(toolbar)
        layout.addWidget(self.summary_label)
        layout.addWidget(splitter)
        self.setCentralWidget(container)
        self.statusBar().showMessage("就绪")

    def _connect_signals(self) -> None:
        self.monitoring.checking.connect(self._on_checking)
        self.monitoring.result_ready.connect(self._on_probe_result)
        self.recording_manager.status_changed.connect(self._on_recording_status)
        self.recording_manager.output_changed.connect(self._on_recording_output)
        self.recording_manager.file_created.connect(self._on_file_created)

    def _refresh_table(self) -> None:
        ordered_rooms = list(self.rooms.values())
        self.table.setRowCount(len(ordered_rooms))
        for row_index, room in enumerate(ordered_rooms):
            name = room.anchor_name or room.name
            self.table.setItem(row_index, 0, QTableWidgetItem(name))

            url_item = QTableWidgetItem(room.url)
            url_item.setToolTip(room.url)
            self.table.setItem(row_index, 1, url_item)
            self.table.setItem(row_index, 2, QTableWidgetItem(room.platform))

            live_item = QTableWidgetItem(LIVE_STATUS_TEXT[room.live_status])
            live_item.setToolTip(room.last_error or room.title)
            self._color_status_item(live_item, room.live_status.value)
            self.table.setItem(row_index, 3, live_item)

            recording_item = QTableWidgetItem(
                RECORDING_STATUS_TEXT[room.recording_status]
            )
            recording_item.setToolTip(room.output_file or room.last_error)
            self._color_status_item(recording_item, room.recording_status.value)
            self.table.setItem(row_index, 4, recording_item)
            self.table.setItem(
                row_index,
                5,
                QTableWidgetItem(self._format_checked_time(room.last_checked_at)),
            )

            monitor_button = QPushButton(
                "停止监控" if room.monitor_enabled else "开启监控"
            )
            monitor_button.clicked.connect(
                lambda _checked=False, room_id=room.id: self._toggle_monitor(room_id)
            )
            self.table.setCellWidget(row_index, 6, monitor_button)

            recording_active = self.recording_manager.is_recording(room.id)
            record_button = QPushButton("停止录制" if recording_active else "开始录制")
            record_button.setEnabled(
                room.recording_status
                not in {RecordingStatus.STARTING, RecordingStatus.STOPPING}
            )
            record_button.clicked.connect(
                lambda _checked=False, room_id=room.id: self._toggle_recording(room_id)
            )
            self.table.setCellWidget(row_index, 7, record_button)

            delete_button = QPushButton("删除")
            delete_button.clicked.connect(
                lambda _checked=False, room_id=room.id: self._delete_room(room_id)
            )
            self.table.setCellWidget(row_index, 8, delete_button)

        live_count = sum(room.live_status == LiveStatus.LIVE for room in ordered_rooms)
        recording_count = len(self.recording_manager.active_room_ids())
        monitoring_count = sum(room.monitor_enabled for room in ordered_rooms)
        self.summary_label.setText(
            f"直播间 {len(ordered_rooms)} 个　正在监控 {monitoring_count} 个　"
            f"直播中 {live_count} 个　录制中 {recording_count} 个"
        )

    @staticmethod
    def _color_status_item(item: QTableWidgetItem, status: str) -> None:
        color_map = {
            LiveStatus.LIVE.value: QColor(36, 138, 61, 45),
            LiveStatus.ERROR.value: QColor(196, 43, 28, 45),
            LiveStatus.CHECKING.value: QColor(175, 117, 0, 45),
            RecordingStatus.RECORDING.value: QColor(196, 43, 28, 45),
            RecordingStatus.FAILED.value: QColor(196, 43, 28, 45),
            RecordingStatus.STARTING.value: QColor(175, 117, 0, 45),
            RecordingStatus.STOPPING.value: QColor(175, 117, 0, 45),
        }
        color = color_map.get(status)
        if color:
            item.setBackground(color)

    @staticmethod
    def _format_checked_time(value: str) -> str:
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%H:%M:%S")
        except ValueError:
            return value

    def _add_room(self) -> None:
        dialog = AddRoomDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        room = dialog.room()
        try:
            self.repository.add(room)
        except DuplicateRoomError as error:
            QMessageBox.warning(self, "无法添加", str(error))
            return
        self.rooms[room.id] = room
        self._append_log(room, "直播间已添加")
        self._refresh_table()
        if room.monitor_enabled:
            self.monitoring.probe_now(room)

    def _toggle_monitor(self, room_id: str) -> None:
        room = self.rooms[room_id]
        room.monitor_enabled = not room.monitor_enabled
        self.repository.set_monitor_enabled(room_id, room.monitor_enabled)
        state = "开启" if room.monitor_enabled else "停止"
        self._append_log(room, f"已{state}监控")
        if room.monitor_enabled:
            self.monitoring.probe_now(room)
        self._refresh_table()

    def _toggle_recording(self, room_id: str) -> None:
        room = self.rooms[room_id]
        if self.recording_manager.is_recording(room_id):
            self.recording_manager.stop(room_id)
            return
        room.recording_status = RecordingStatus.STARTING
        self._append_log(room, "正在获取最新直播源")
        self._refresh_table()
        self.monitoring.probe_now(room, purpose="record")

    def _delete_room(self, room_id: str) -> None:
        room = self.rooms[room_id]
        if self.recording_manager.is_recording(room_id):
            QMessageBox.warning(self, "无法删除", "请先停止该直播间的录制")
            return
        result = QMessageBox.question(
            self,
            "删除直播间",
            f"确定删除“{room.name}”吗？录制文件不会被删除。",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self.monitoring.forget(room_id)
        self.repository.delete(room_id)
        self.rooms.pop(room_id, None)
        self._refresh_table()

    def _refresh_all(self) -> None:
        for room in self.rooms.values():
            if room.monitor_enabled:
                self.monitoring.probe_now(room)
        self.statusBar().showMessage("正在刷新已开启监控的直播间", 3000)

    def _open_settings(self) -> None:
        if SettingsDialog(self.preferences, self).exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("设置已保存", 3000)

    def _open_output_directory(self) -> None:
        output = Path(self.preferences.output_directory)
        output.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

    def _on_checking(self, room_id: str) -> None:
        room = self.rooms.get(room_id)
        if not room:
            return
        room.live_status = LiveStatus.CHECKING
        self._refresh_table()

    def _on_probe_result(
        self,
        room_id: str,
        result: ProbeResult,
        purpose: str,
    ) -> None:
        room = self.rooms.get(room_id)
        if not room:
            return
        room.live_status = result.status
        room.anchor_name = result.anchor_name or room.anchor_name
        room.title = result.title
        room.stream_url = result.stream_url
        room.last_checked_at = result.checked_at
        room.last_error = result.error

        if result.error:
            self._append_log(room, f"检测失败：{result.error}")
        elif result.is_live:
            self._append_log(room, "当前正在直播")
        else:
            self._append_log(room, "当前未开播")

        if purpose == "record":
            if result.is_live and result.stream_url:
                self.recording_manager.start(
                    room,
                    result.stream_url,
                    self.preferences.output_directory,
                )
            else:
                room.recording_status = RecordingStatus.FAILED
                message = result.error or "直播间当前未开播，无法开始录制"
                QMessageBox.warning(self, "无法录制", message)
        self._refresh_table()

    def _on_recording_status(self, room_id: str, status: str, message: str) -> None:
        room = self.rooms.get(room_id)
        if not room:
            return
        room.recording_status = RecordingStatus(status)
        if room.recording_status == RecordingStatus.FAILED:
            room.last_error = message
        self._append_log(room, message)
        self._refresh_table()

    def _on_recording_output(self, room_id: str, output: str) -> None:
        room = self.rooms.get(room_id)
        if room:
            self._append_log(room, f"FFmpeg：{output}")

    def _on_file_created(self, room_id: str, output_file: str) -> None:
        room = self.rooms.get(room_id)
        if room:
            room.output_file = output_file
            self._append_log(room, f"保存到：{output_file}")

    def _append_log(self, room: Room, message: str) -> None:
        now = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{now}] [{room.name}] {message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closed:
            event.accept()
            return
        if self.recording_manager.active_room_ids():
            result = QMessageBox.question(
                self,
                "退出应用",
                "仍有直播间正在录制。退出会安全停止所有录制，是否继续？",
            )
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closed = True
        self.monitoring.stop()
        self.recording_manager.shutdown()
        self.repository.close()
        event.accept()
