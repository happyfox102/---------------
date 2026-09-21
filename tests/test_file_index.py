import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from friday.engine import Engine
from friday.storage import Store


class FileCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.store.config["search_roots"] = [str(self.root / "files")]
        self.files = self.root / "files"
        self.files.mkdir()
        self.engine = Engine(self.store, Mock())

    def index(self):
        self.engine.file_index.refresh(force=True)
        self.engine.file_index.thread.join(10)
        self.assertTrue(self.engine.file_index.ready)

    def test_exact_folder_and_file_stem_win_over_partial_names(self):
        folder = self.files / "Код"
        folder.mkdir()
        (self.files / "Код старый").mkdir()
        file = self.files / "Рейтинг.xlsx"
        file.touch()
        (self.files / "Рейтинг прошлый.xlsx").touch()
        self.index()
        with patch("friday.engine.os.startfile", create=True) as start:
            self.engine.execute("открой папку код")
            start.assert_called_with(str(folder))
            self.engine.execute("открой файл рейтинг")
            start.assert_called_with(str(file))
        self.engine.windows.open_app.assert_not_called()

    def test_duplicate_names_require_number_and_executable_requires_confirmation(self):
        for name in ("a", "b"):
            (self.files / name).mkdir()
            (self.files / name / "рейтинг.txt").touch()
        exe = self.files / "Тест.exe"
        exe.touch()
        self.index()
        with patch("friday.engine.os.startfile", create=True) as start:
            self.assertIn("несколько", self.engine.execute("открой файл рейтинг"))
            start.assert_not_called()
            self.engine.execute("два")
            start.assert_called_once_with(str(self.files / "b/рейтинг.txt"))
            start.reset_mock()
            self.assertIn("подтверждаю", self.engine.execute("запусти файл тест"))
            start.assert_not_called()
            self.engine.execute("подтверждаю")
            start.assert_called_once_with(str(exe))

    def test_cache_reuse_deleted_files_and_changed_scope(self):
        file = self.files / "Отчёт.txt"
        file.touch()
        self.index()
        with patch("os.scandir", side_effect=AssertionError("Must use index")):
            self.assertEqual(self.engine.file_index.find("отчет", "file"), [file])
        file.unlink()
        self.assertEqual(self.engine.file_index.find("отчет", "file"), [])
        self.store.config["search_roots"] = []
        self.assertEqual(self.engine.file_index.find("отчет", "file"), [])
