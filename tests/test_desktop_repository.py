import tempfile
import unittest
from pathlib import Path

from desktop_app.domain import Room
from desktop_app.repository import DuplicateRoomError, RoomRepository


class RoomRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "rooms.db"
        self.repository = RoomRepository(database_path)

    def tearDown(self):
        self.repository.close()
        self.temp_directory.cleanup()

    def test_round_trips_room_and_monitor_state(self):
        room = Room.create("测试主播", "https://live.douyin.com/123")
        self.repository.add(room)
        self.repository.set_monitor_enabled(room.id, False)

        saved = self.repository.list_rooms()

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].name, "测试主播")
        self.assertFalse(saved[0].monitor_enabled)

    def test_persists_automatically_detected_room_name(self):
        room = Room.create("", "https://live.douyin.com/123")
        self.repository.add(room)

        self.repository.set_name(room.id, "自动识别主播")

        self.assertEqual(self.repository.list_rooms()[0].name, "自动识别主播")

    def test_rejects_duplicate_url_case_insensitively(self):
        self.repository.add(Room.create("一", "https://LIVE.DOUYIN.COM/123"))

        with self.assertRaises(DuplicateRoomError):
            self.repository.add(Room.create("二", "https://live.douyin.com/123"))

    def test_deletes_room(self):
        room = Room.create("测试主播", "https://live.douyin.com/123")
        self.repository.add(room)

        self.repository.delete(room.id)

        self.assertEqual(self.repository.list_rooms(), [])


if __name__ == "__main__":
    unittest.main()
