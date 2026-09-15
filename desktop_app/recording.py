from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .domain import RecordingStatus, Room
from .ffmpeg_command import build_ffmpeg_arguments, build_output_path, find_ffmpeg


class RecordingManager(QObject):
    status_changed = Signal(str, str, str)
    output_changed = Signal(str, str)
    file_created = Signal(str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._processes: dict[str, QProcess] = {}
        self._requested_stops: set[str] = set()

    def is_recording(self, room_id: str) -> bool:
        process = self._processes.get(room_id)
        return bool(process and process.state() != QProcess.ProcessState.NotRunning)

    def active_room_ids(self) -> set[str]:
        return {
            room_id
            for room_id, process in self._processes.items()
            if process.state() != QProcess.ProcessState.NotRunning
        }

    def start(self, room: Room, stream_url: str, output_directory: str) -> None:
        if self.is_recording(room.id):
            return

        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            self.status_changed.emit(
                room.id,
                RecordingStatus.FAILED.value,
                "未找到 FFmpeg，请安装 FFmpeg 或设置 FFMPEG_PATH",
            )
            return

        output_file = build_output_path(output_directory, room)
        process = QProcess(self)
        process.setProgram(ffmpeg)
        process.setArguments(build_ffmpeg_arguments(stream_url, output_file))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.started.connect(
            lambda room_id=room.id, path=str(output_file): self._on_started(room_id, path)
        )
        process.readyReadStandardOutput.connect(
            lambda room_id=room.id: self._read_output(room_id)
        )
        process.errorOccurred.connect(
            lambda _error, room_id=room.id: self._on_process_error(room_id)
        )
        process.finished.connect(
            lambda code, _status, room_id=room.id: self._on_finished(room_id, code)
        )
        self._processes[room.id] = process
        self.status_changed.emit(room.id, RecordingStatus.STARTING.value, "正在启动 FFmpeg")
        process.start()

    def stop(self, room_id: str) -> None:
        process = self._processes.get(room_id)
        if not process or process.state() == QProcess.ProcessState.NotRunning:
            return
        self._requested_stops.add(room_id)
        self.status_changed.emit(room_id, RecordingStatus.STOPPING.value, "正在安全停止录制")
        process.write(b"q\n")
        QTimer.singleShot(5000, lambda: self._force_stop_if_needed(room_id))

    def shutdown(self) -> None:
        for room_id in list(self.active_room_ids()):
            process = self._processes[room_id]
            self._requested_stops.add(room_id)
            process.write(b"q\n")
            if not process.waitForFinished(5000):
                process.terminate()
            if not process.waitForFinished(2000):
                process.kill()
                process.waitForFinished(1000)

    def _on_started(self, room_id: str, output_file: str) -> None:
        self.file_created.emit(room_id, output_file)
        self.status_changed.emit(room_id, RecordingStatus.RECORDING.value, "正在录制")

    def _read_output(self, room_id: str) -> None:
        process = self._processes.get(room_id)
        if not process:
            return
        output = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        if output:
            self.output_changed.emit(room_id, output)

    def _on_process_error(self, room_id: str) -> None:
        process = self._processes.get(room_id)
        if not process or process.state() != QProcess.ProcessState.NotRunning:
            return
        self.status_changed.emit(room_id, RecordingStatus.FAILED.value, process.errorString())

    def _on_finished(self, room_id: str, exit_code: int) -> None:
        requested = room_id in self._requested_stops
        self._requested_stops.discard(room_id)
        self._processes.pop(room_id, None)
        if requested or exit_code == 0:
            self.status_changed.emit(room_id, RecordingStatus.IDLE.value, "录制已停止")
        else:
            self.status_changed.emit(
                room_id,
                RecordingStatus.FAILED.value,
                f"FFmpeg 异常退出，返回码 {exit_code}",
            )

    def _force_stop_if_needed(self, room_id: str) -> None:
        process = self._processes.get(room_id)
        if process and process.state() != QProcess.ProcessState.NotRunning:
            process.terminate()
            QTimer.singleShot(
                2000,
                lambda: process.kill()
                if process.state() != QProcess.ProcessState.NotRunning
                else None,
            )
