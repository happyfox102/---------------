"""Controlled local integration checks. Does not connect VPN or call a paid API."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from friday.qt import QtWidgets as W, QtCore as C, QtGui as G, Signal
from friday.credentials import Secrets
from friday.computer_control import ComputerControl
from friday.storage import Store
from friday.vpn import VPN
from friday.windows_ocr import read


def main():
    report = {}
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp))
        secrets = Secrets(Path(temp)/'secrets')
        secrets.set('test', 'integration-test-only')
        assert secrets.get('test') == 'integration-test-only'
        report['dpapi_roundtrip'] = True
        service = VPN(store, secrets)
        profile = service.add_server('Friday integration test', '198.51.100.1', 'Ikev2')
        try:
            assert profile['entry'] in service.statuses()
            report['windows_profile_create_status'] = True
        finally:
            service.remove(profile)
        assert profile['entry'] not in service.statuses()
        report['windows_profile_removed'] = True
        app = W.QApplication([])
        pixmap = G.QPixmap(700, 120); pixmap.fill(G.QColor('white'))
        painter = G.QPainter(pixmap); painter.setFont(G.QFont('Arial', 30)); painter.setPen(G.QColor('black'))
        painter.drawText(25, 75, 'ПЯТНИЦА ТЕСТ 123'); painter.end()
        path = Path(temp)/'ocr.png'; assert pixmap.save(str(path))
        result = read(path)
        assert '123' in result['text'] and 'ПЯТНИЦА' in result['text'].upper(), repr(result['text'])
        report['windows_ocr_synthetic_image'] = True

        class Harness(W.QWidget):
            finished = Signal(str)
            def __init__(self):
                super().__init__(); self.setWindowTitle('Friday keyboard integration test')
                layout = W.QVBoxLayout(self)
                self.edit = W.QLineEdit(); layout.addWidget(self.edit)
                self.finished.connect(self.complete)
                self.error = None
            def start(self):
                self.show(); self.raise_(); self.activateWindow(); self.edit.setFocus()
                C.QTimer.singleShot(600, self.type)
            def type(self):
                def work():
                    try:
                        import win32gui, win32process
                        assert win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1] == os.getpid(), 'Test window is not focused'
                        ComputerControl(None, threading.Event()).type_text('Hello, Пятница! 123.')
                        self.finished.emit('')
                    except Exception as exc: self.finished.emit(str(exc))
                threading.Thread(target=work, daemon=True).start()
            def complete(self, error):
                self.error = error
                C.QTimer.singleShot(200, app.quit)
        window = Harness(); C.QTimer.singleShot(0, window.start)
        watchdog = C.QTimer(); watchdog.setSingleShot(True); watchdog.timeout.connect(app.quit); watchdog.start(20000)
        app.exec()
        assert window.error == '', window.error or 'Keyboard test timeout'
        assert window.edit.text() == 'Hello, Пятница! 123.', 'Unicode text mismatch'
        report['sendinput_unicode_exact'] = True
        window.close()
    report['ok'] = True
    (ROOT/'artifacts/new-features-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__': main()
