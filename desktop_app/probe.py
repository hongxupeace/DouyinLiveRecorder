from __future__ import annotations

import asyncio
import os
from typing import Protocol
from urllib.parse import urlparse

import httpx

from .domain import ProbeResult, ProbeSettings, default_room_name, detect_platform


class LiveProbe(Protocol):
    async def probe(self, url: str, settings: ProbeSettings) -> ProbeResult:
        ...


class DouyinProbe:
    """Adapter over the existing Douyin spider and stream parsing code."""

    async def probe(self, url: str, settings: ProbeSettings) -> ProbeResult:
        try:
            # Deferred import keeps the GUI responsive while the legacy package
            # loads. The first desktop release only uses the Python Douyin
            # signer, so it does not need the legacy Node.js auto-installer.
            os.environ.setdefault("DOUYIN_RECORDER_SKIP_NODE_CHECK", "1")
            from src import spider, stream

            if "v.douyin.com" in url or "/user/" in url:
                room_data = await asyncio.wait_for(
                    spider.get_douyin_app_stream_data(
                        url=url,
                        proxy_addr=settings.proxy or None,
                        cookies=settings.cookie or None,
                    ),
                    timeout=settings.timeout_seconds,
                )
            else:
                room_data = await asyncio.wait_for(
                    spider.get_douyin_web_stream_data(
                        url=url,
                        proxy_addr=settings.proxy or None,
                        cookies=settings.cookie or None,
                    ),
                    timeout=settings.timeout_seconds,
                )

            if not isinstance(room_data, dict):
                raise TypeError("抖音解析器返回了无效数据")

            stream_info = await asyncio.wait_for(
                stream.get_douyin_stream_url(
                    room_data,
                    settings.quality,
                    settings.proxy or None,
                ),
                timeout=settings.timeout_seconds,
            )
            if not isinstance(stream_info, dict):
                raise TypeError("抖音流地址解析失败")

            return ProbeResult(
                is_live=bool(stream_info.get("is_live")),
                anchor_name=str(stream_info.get("anchor_name") or ""),
                title=str(stream_info.get("title") or ""),
                stream_url=str(stream_info.get("record_url") or ""),
            )
        except Exception as error:  # noqa: BLE001 - isolates the legacy adapter.
            return ProbeResult(is_live=False, error=str(error))


class DirectStreamProbe:
    """Check a direct m3u8/flv source without downloading the whole stream."""

    async def probe(self, url: str, settings: ProbeSettings) -> ProbeResult:
        proxy = settings.proxy or None
        headers = {
            "Range": "bytes=0-1023",
            "User-Agent": "DouyinLiveRecorder-Desktop/1.0",
        }
        try:
            async with httpx.AsyncClient(
                proxy=proxy,
                timeout=settings.timeout_seconds,
                verify=True,
                follow_redirects=True,
            ) as client, client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                first_chunk = b""
                async for chunk in response.aiter_bytes():
                    first_chunk = chunk
                    break
                if not first_chunk:
                    raise RuntimeError("直播源没有返回数据")

            if detect_platform(url) == "m3u8" and b"#EXTM3U" not in first_chunk:
                raise RuntimeError("返回内容不是有效的 m3u8 播放列表")

            return ProbeResult(
                is_live=True,
                anchor_name=default_room_name(url),
                stream_url=url,
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as error:
            return ProbeResult(is_live=False, error=str(error))


class ProbeRegistry:
    def __init__(
        self,
        douyin_probe: LiveProbe | None = None,
        direct_probe: LiveProbe | None = None,
    ):
        self._douyin_probe = douyin_probe or DouyinProbe()
        self._direct_probe = direct_probe or DirectStreamProbe()

    async def probe(self, url: str, settings: ProbeSettings) -> ProbeResult:
        platform = detect_platform(url)
        if platform == "douyin":
            return await self._douyin_probe.probe(url, settings)
        return await self._direct_probe.probe(url, settings)


def display_host(url: str) -> str:
    return urlparse(url).netloc
