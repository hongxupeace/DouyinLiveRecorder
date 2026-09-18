from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?，。；：！？、）》】」』}"


class LiveStatus(str, Enum):
    UNKNOWN = "unknown"
    CHECKING = "checking"
    LIVE = "live"
    OFFLINE = "offline"
    ERROR = "error"


class RecordingStatus(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass(slots=True)
class Room:
    id: str
    name: str
    url: str
    platform: str
    monitor_enabled: bool = True
    created_at: str = field(default_factory=lambda: utc_now())
    updated_at: str = field(default_factory=lambda: utc_now())
    live_status: LiveStatus = LiveStatus.UNKNOWN
    recording_status: RecordingStatus = RecordingStatus.IDLE
    anchor_name: str = ""
    title: str = ""
    stream_url: str = ""
    last_checked_at: str = ""
    last_error: str = ""
    output_file: str = ""

    @classmethod
    def create(cls, name: str, url: str, monitor_enabled: bool = True) -> Room:
        clean_url = normalize_url(url)
        return cls(
            id=str(uuid4()),
            name=name.strip() or default_room_name(clean_url),
            url=clean_url,
            platform=detect_platform(clean_url),
            monitor_enabled=monitor_enabled,
        )


@dataclass(frozen=True, slots=True)
class ProbeSettings:
    cookie: str = ""
    proxy: str = ""
    quality: str = "OD"
    timeout_seconds: int = 25


@dataclass(frozen=True, slots=True)
class ProbeResult:
    is_live: bool
    anchor_name: str = ""
    title: str = ""
    stream_url: str = ""
    error: str = ""
    checked_at: str = field(default_factory=lambda: utc_now())

    @property
    def status(self) -> LiveStatus:
        if self.error:
            return LiveStatus.ERROR
        return LiveStatus.LIVE if self.is_live else LiveStatus.OFFLINE


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_platform(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host.endswith("douyin.com"):
        return "douyin"
    if path.endswith(".m3u8"):
        return "m3u8"
    if path.endswith(".flv"):
        return "flv"
    raise ValueError("首版仅支持抖音直播间以及 m3u8/flv 直播源")


def normalize_url(text: str) -> str:
    value = text.strip()
    if not value:
        raise ValueError("分享内容或直播间地址不能为空")

    candidates = [
        match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        for match in URL_PATTERN.finditer(value)
    ]
    if not candidates:
        candidates = [value]

    for candidate in candidates:
        try:
            normalized = _normalize_url_candidate(candidate)
            detect_platform(normalized)
            return normalized
        except ValueError:
            continue

    raise ValueError("分享内容中没有找到受支持的抖音或 m3u8/flv 直播地址")


def _normalize_url_candidate(url: str) -> str:
    value = url.strip()
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入有效的 http/https 直播间地址")
    return value


def default_room_name(url: str) -> str:
    parsed = urlparse(url)
    identifier = Path(parsed.path.rstrip("/")).name
    return identifier or parsed.netloc
