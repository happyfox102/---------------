"""On-demand Screen Vision adapters. It never polls or uploads the screen."""
from pathlib import Path
import os
import time


class ScreenCapture:
    def __init__(self, store):
        self.store = store

    def capture(self, active=False):
        folder = self.store.data / 'screenshots'; folder.mkdir(exist_ok=True)
        path = self.store.unique_path('screenshots', time.strftime('%Y-%m-%d %H-%M-%S'), '.png')
        from .system_actions import screenshot
        screenshot(path, active=active)
        return {'path': str(path), 'active': active, 'verified': path.is_file()}


class UIAutomation:
    def windows(self):
        if os.name != 'nt':
            return []
        import win32gui
        result = []
        def visit(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    result.append({'handle': hwnd, 'title': title, 'rect': win32gui.GetWindowRect(hwnd)})
        win32gui.EnumWindows(visit, None)
        return result

    def active_window(self):
        if os.name != 'nt':
            return {'title': '', 'handle': None}
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return {'handle': hwnd, 'title': win32gui.GetWindowText(hwnd), 'rect': win32gui.GetWindowRect(hwnd)}

    def find_window(self, text):
        query = text.casefold().strip()
        return [item for item in self.windows() if query in item['title'].casefold()]


class OCR:
    """Optional OCR adapter. No fake result is returned when OCR is absent."""
    def __init__(self):
        self.backend = 'windows' if os.name == 'nt' else None
        try:
            import pytesseract  # noqa: F401
            self.backend = 'tesseract'
        except ImportError:
            pass

    def read(self, path):
        if self.backend == 'windows':
            from .windows_ocr import read
            return read(path)
        if not self.backend:
            raise RuntimeError('OCR не установлен. Установите Tesseract и pytesseract для чтения текста на экране.')
        import pytesseract
        from PIL import Image
        return {'text': pytesseract.image_to_string(Image.open(path), lang='rus+eng'), 'backend': self.backend}


class VisionAnalyzer:
    def __init__(self, store):
        self.capture = ScreenCapture(store)
        self.ui = UIAutomation()
        self.ocr = OCR()

    def snapshot(self, active=False):
        return self.capture.capture(active)

    def windows(self):
        return self.ui.windows()

    def active(self):
        return self.ui.active_window()

    def find_window(self, text):
        return self.ui.find_window(text)

    def ocr_read(self, path):
        return self.ocr.read(path)
