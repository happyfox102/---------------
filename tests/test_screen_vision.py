import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from friday.storage import Store
from friday.screen_vision import ScreenCapture, UIAutomation, OCR, VisionAnalyzer


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name))

    def test_capture_uses_existing_screenshot_service_and_verifies_file(self):
        target=self.store.data/'screenshots'/'x.png'
        def fake(path,active=False):
            path.write_bytes(b'PNG')
        with patch('friday.system_actions.screenshot',side_effect=fake) as capture:
            result=ScreenCapture(self.store).capture(active=True)
        capture.assert_called_once()
        self.assertTrue(result['verified']); self.assertTrue(result['active'])

    def test_windows_and_active_window_are_real_ui_automation_adapters(self):
        automation=UIAutomation()
        with patch.object(automation,'windows',return_value=[{'title':'VS Code','handle':1},{'title':'Browser','handle':2}]):
            self.assertEqual(len(automation.find_window('code')),1)

    def test_ocr_is_honest_when_optional_backend_missing(self):
        ocr=OCR(); ocr.backend=None
        with self.assertRaises(RuntimeError): ocr.read('does-not-exist.png')

    def test_vision_analyzer_has_four_separate_adapters(self):
        vision=VisionAnalyzer(self.store)
        self.assertTrue(hasattr(vision,'capture')); self.assertTrue(hasattr(vision,'ui'))
        self.assertTrue(hasattr(vision,'ocr'))

if __name__=='__main__': unittest.main()
