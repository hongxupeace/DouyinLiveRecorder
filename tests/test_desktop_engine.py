import tempfile
import unittest
from pathlib import Path

from desktop_app.domain import ProbeResult, ProbeSettings, Room
from desktop_app.ffmpeg_command import (
    build_ffmpeg_arguments,
    build_output_path,
    safe_filename,
)
from desktop_app.probe import ProbeRegistry


class FakeProbe:
    def __init__(self, result: ProbeResult):
        self.result = result
        self.calls = []

    async def probe(self, url: str, settings: ProbeSettings) -> ProbeResult:
        self.calls.append((url, settings))
        return self.result


class ProbeRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_douyin_to_douyin_adapter(self):
        expected = ProbeResult(
            is_live=True,
            anchor_name="主播",
            stream_url="https://stream.example/live.flv",
        )
        douyin = FakeProbe(expected)
        direct = FakeProbe(ProbeResult(is_live=False))
        registry = ProbeRegistry(douyin_probe=douyin, direct_probe=direct)

        actual = await registry.probe(
            "https://live.douyin.com/123",
            ProbeSettings(cookie="cookie-value"),
        )

        self.assertEqual(actual, expected)
        self.assertEqual(len(douyin.calls), 1)
        self.assertEqual(direct.calls, [])

    async def test_routes_direct_stream_to_direct_adapter(self):
        direct = FakeProbe(ProbeResult(is_live=True, stream_url="https://x/live.m3u8"))
        registry = ProbeRegistry(
            douyin_probe=FakeProbe(ProbeResult(is_live=False)),
            direct_probe=direct,
        )

        await registry.probe("https://x/live.m3u8", ProbeSettings())

        self.assertEqual(len(direct.calls), 1)


class FfmpegCommandTests(unittest.TestCase):
    def test_sanitizes_windows_filename(self):
        self.assertEqual(safe_filename('主播<一>:"测试"'), "主播_一___测试")

    def test_builds_segment_safe_ts_recording_command(self):
        arguments = build_ffmpeg_arguments(
            "https://stream.example/live.m3u8",
            "C:/Videos/room.ts",
        )

        self.assertIn("-reconnect", arguments)
        self.assertEqual(arguments[-3:], ["-f", "mpegts", "C:/Videos/room.ts"])

    def test_builds_room_directory_and_ts_filename(self):
        room = Room.create('主播:"一"', "https://live.douyin.com/123")
        with tempfile.TemporaryDirectory() as temp_directory:
            output = build_output_path(temp_directory, room)

            self.assertEqual(output.parent.name, "主播__一")
            self.assertEqual(output.suffix, ".ts")
            self.assertTrue(Path(output).parent.is_dir())


if __name__ == "__main__":
    unittest.main()
