"""Offscreen UI integration check; no microphone, voice playback or PC actions."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import tempfile
import time
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.qt import QApplication, BINDING, QtGui, QMessageBox
from friday.storage import Store
from friday.ui import Window, Settings, STYLE


def main():
    app = QApplication([])
    for filename in ("segoeui.ttf", "segoeuib.ttf"):
        QtGui.QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename))
    def warning(parent, title, text):
        raise AssertionError(f"Unexpected dialog: {title}: {text}")
    QMessageBox.warning = warning
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp))
        store.config["speak"] = False
        store.config["search_roots"] = [temp]
        window = Window(store)
        window.show()
        app.processEvents()
        for command in ("создай таблицу Проверка", "запиши 1500 в B3", "прочитай B3", "таймер на 5 минут"):
            window.submit(command)
            deadline = time.monotonic() + 10
            while window.busy.is_set() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            assert not window.busy.is_set(), "Worker did not finish"
        assert "B3: 1500" in window.dialogue.toPlainText()
        assert "Проверка.xlsx" in window.book_label.text()
        assert "Таймер завершён" in window.reminder_label.text()
        app.processEvents()
        folder = ROOT / "artifacts"
        folder.mkdir(exist_ok=True)
        window.grab().save(str(folder / "window.png"))
        settings = Settings(store, window)
        settings.show()
        app.processEvents()
        settings.grab().save(str(folder / "settings.png"))
        settings.save()
        assert store.config["speech_backend"] == "google"
        window.hide()
        with patch.object(window.listener, "start", return_value=True) as start, patch.object(window.listener, "stop") as stop, patch.object(window, "microphone_feedback") as feedback:
            window.hotkey.activated.emit()
            app.processEvents()
            start.assert_called_once_with(background=True, direct=True)
            assert window.accept_voice and window.direct_listening and not window.isVisible()
            window.listener.signals.ready.emit()
            app.processEvents()
            feedback.assert_called_with(True)
            window.hotkey.activated.emit()
            app.processEvents()
            assert not window.accept_voice and not window.direct_listening
            stop.assert_called_once()
            feedback.assert_called_with(False)
        window.close()
        window.speaker.thread.join(2)
        if window.engine.file_index.thread:
            window.engine.file_index.thread.join(10)
        app.processEvents()
    print(f"UI OK ({BINDING}): command worker, Excel, reminders, settings, screenshots.")


if __name__ == "__main__":
    main()
