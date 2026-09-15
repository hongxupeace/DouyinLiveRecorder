import unittest

from desktop_app.domain import LiveStatus, ProbeResult, Room, detect_platform


class DomainTests(unittest.TestCase):
    def test_creates_douyin_room_and_normalizes_scheme(self):
        room = Room.create("", "live.douyin.com/123456")

        self.assertEqual(room.url, "https://live.douyin.com/123456")
        self.assertEqual(room.name, "123456")
        self.assertEqual(room.platform, "douyin")
        self.assertTrue(room.monitor_enabled)

    def test_detects_direct_stream_types_with_query_string(self):
        self.assertEqual(
            detect_platform("https://example.com/live/index.m3u8?token=abc"),
            "m3u8",
        )
        self.assertEqual(detect_platform("https://example.com/live.flv"), "flv")

    def test_rejects_unsupported_platform(self):
        with self.assertRaisesRegex(ValueError, "首版仅支持"):
            Room.create("测试", "https://example.com/live")

    def test_probe_result_maps_to_live_status(self):
        self.assertEqual(ProbeResult(is_live=True).status, LiveStatus.LIVE)
        self.assertEqual(ProbeResult(is_live=False).status, LiveStatus.OFFLINE)
        self.assertEqual(
            ProbeResult(is_live=False, error="timeout").status,
            LiveStatus.ERROR,
        )


if __name__ == "__main__":
    unittest.main()
