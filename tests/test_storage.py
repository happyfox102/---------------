import json
import tempfile
import threading
import unittest
from pathlib import Path

from friday.storage import Store
from friday.engine import Engine


class StorageTests(unittest.TestCase):
    def test_concurrent_reminders_do_not_lose_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp))
            engine = Engine(store)
            threads = [threading.Thread(target=engine.add_reminder, args=(1900000000 + i, str(i))) for i in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(engine.reminders()), 12)

    def test_corrupt_data_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp))
            path = store.data / "settings.json"
            path.write_text("broken")
            with self.assertRaises(RuntimeError):
                Store(Path(temp))
            self.assertEqual(path.read_text(), "broken")

    def test_document_name_cannot_escape_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp))
            path = store.unique_path("documents", "../../report", ".txt")
            self.assertEqual(path.parent, store.data / "documents")
            self.assertTrue(store.unique_path("documents", "CON", ".txt").name.startswith("_"))


if __name__ == "__main__":
    unittest.main()
