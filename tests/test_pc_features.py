import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from friday.pc_services import category, scan_disk, Optimizer
from friday.storage import Store
from friday.engine import Engine


class PCFeaturesTests(unittest.TestCase):
    def test_categories_prefer_game_installation_over_extensions(self):
        self.assertEqual(category(Path('D:/SteamLibrary/steamapps/common/Game/movie.mp4')), 'Игры')
        self.assertEqual(category(Path('C:/Users/me/photo.JPG')), 'Фото')
        self.assertEqual(category(Path('C:/Program Files/App/video.mp4')), 'Программы')

    def test_scan_counts_files_and_honors_cancellation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            (root / 'a.txt').write_bytes(b'abc')
            (root / 'b.jpg').write_bytes(b'12345')
            results = []
            cancel = threading.Event()
            scan_disk(root, cancel, lambda *x: results.append(x))
            self.assertEqual(results[-1][0], {'Документы': 3, 'Фото': 5})
            self.assertTrue(results[-1][3])
            cancel.set(); results.clear()
            scan_disk(root, cancel, lambda *x: results.append(x))
            self.assertEqual(results[-1][1], 0)
            self.assertFalse(results[-1][3])

    def test_voice_routes_all_pages_and_recording(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = Engine(Store(Path(temp)), Mock())
            engine.ui_action = Mock()
            for text, action in [('открой мой пк', 'overview'), ('открой хранилище', 'disk'), ('включи игровой режим', 'game'), ('ускорь пк', 'optimize'), ('начни запись экрана и камеры', 'record_camera'), ('продолжи запись', 'record_resume'), ('останови запись', 'record_stop')]:
                engine.execute(text)
                engine.ui_action.assert_called_with(action)

    def test_restore_never_changes_reused_pid(self):
        with tempfile.TemporaryDirectory() as temp:
            optimizer = Optimizer(Store(Path(temp)))
            optimizer.saved = {'processes': {'123': [100, 32]}}
            proc = Mock(); proc.create_time.return_value = 200
            with patch('friday.pc_services.psutil.Process', return_value=proc):
                optimizer.restore()
            proc.nice.assert_not_called()

    def test_optimizer_protects_foreground_and_other_users(self):
        import psutil
        with tempfile.TemporaryDirectory() as temp:
            optimizer = Optimizer(Store(Path(temp)))
            owner = Mock(pid=10); owner.username.return_value = 'me'; owner.parents.return_value = []
            processes = []
            for pid, user in ((11, 'me'), (12, 'other'), (13, 'me')):
                proc = Mock(pid=pid)
                proc.info = {'pid': pid, 'name': 'chrome.exe', 'username': user}
                proc.create_time.return_value = 100
                proc.nice.return_value = psutil.NORMAL_PRIORITY_CLASS
                processes.append(proc)
            with patch('friday.pc_services.foreground_pid', return_value=11), patch('friday.pc_services.psutil.Process', return_value=owner), patch('friday.pc_services.psutil.process_iter', return_value=processes):
                optimizer.lower()
            processes[0].nice.assert_not_called()
            processes[1].nice.assert_not_called()
            processes[2].nice.assert_called_with(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            self.assertEqual(optimizer.saved['processes']['13'][0], 100)

    def test_recording_composition_places_camera_in_corner(self):
        from friday.qt import QtGui as G, QtCore as C
        from friday.recording import composite
        screen = G.QImage(640, 360, G.QImage.Format.Format_RGB32); screen.fill(G.QColor('red'))
        camera = G.QImage(160, 90, G.QImage.Format.Format_RGB32); camera.fill(G.QColor('blue'))
        result = composite(screen, camera, C.QSize(640, 360))
        self.assertEqual(result.pixelColor(10, 10), G.QColor('red'))
        self.assertEqual(result.pixelColor(600, 310), G.QColor('blue'))
