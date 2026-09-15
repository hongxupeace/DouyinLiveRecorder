from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .domain import Room

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


def find_ffmpeg() -> str:
    configured = os.environ.get("FFMPEG_PATH", "").strip()
    executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        Path(configured) if configured else None,
        bundle_root / executable_name,
        Path(sys.executable).parent / executable_name,
        project_root / executable_name,
        project_root / "ffmpeg" / executable_name,
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return str(candidate)
    return shutil.which("ffmpeg") or ""


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" ._")
    return cleaned[:80] or "直播间"


def build_output_path(output_directory: str | Path, room: Room) -> Path:
    root = Path(output_directory).expanduser()
    room_directory = root / safe_filename(room.name)
    room_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    return room_directory / f"{safe_filename(room.name)}_{timestamp}.ts"


def build_ffmpeg_arguments(stream_url: str, output_file: str | Path) -> list[str]:
    return [
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-rw_timeout",
        "15000000",
        "-user_agent",
        USER_AGENT,
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_at_eof",
        "1",
        "-reconnect_delay_max",
        "60",
        "-fflags",
        "+discardcorrupt",
        "-i",
        stream_url,
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "mpegts",
        str(output_file),
    ]
