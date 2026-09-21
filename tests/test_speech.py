import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from friday.speech import Listener


class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = {"vosk_model": self.temp.name, "wake_word": "пятница", "speech_backend": "google"}
        speaker = types.SimpleNamespace(busy=threading.Event(), epoch=0)
        self.listener = Listener(lambda: self.config, speaker, threading.Event(), lambda: False)
        self.recognizer = Mock()
        source = Mock()
        source.__enter__ = Mock(return_value=source)
        source.__exit__ = Mock(return_value=False)
        self.sr = types.SimpleNamespace(Recognizer=Mock(return_value=self.recognizer), Microphone=Mock(return_value=source),
                                        WaitTimeoutError=type("WaitTimeoutError", (Exception,), {}),
                                        UnknownValueError=type("UnknownValueError", (Exception,), {}),
                                        RequestError=type("RequestError", (Exception,), {}))

    def test_background_without_wake_never_sends_audio_to_google(self):
        def local(*args):
            self.listener.cancel.set()
            return "разговор без обращения"
        self.listener.local = local
        with patch.dict("sys.modules", {"speech_recognition": self.sr}):
            self.listener._run(True)
        self.recognizer.recognize_google.assert_not_called()

    def test_direct_mode_accepts_multiple_questions_without_wake_word(self):
        received = []
        self.listener.local = Mock(side_effect=AssertionError("Wake gate must be bypassed"))
        self.recognizer.recognize_google.side_effect = ["который час", "какая дата"]
        def receive(text):
            received.append(text)
            if len(received) == 2:
                self.listener.stop()
        self.listener.signals.text.connect(receive)
        with patch.dict("sys.modules", {"speech_recognition": self.sr}):
            self.listener._run(True, direct=True)
        self.assertEqual(received, ["который час", "какая дата"])
        self.listener.local.assert_not_called()

    def test_stop_during_local_recognition_prevents_cloud_request(self):
        def local(*args):
            self.listener.cancel.set()
            return "пятница открой браузер"
        self.listener.local = local
        with patch.dict("sys.modules", {"speech_recognition": self.sr}):
            self.listener._run(True)
        self.recognizer.recognize_google.assert_not_called()

    def test_stop_during_cloud_recognition_discards_result(self):
        received = []
        self.listener.signals.text.connect(received.append)
        def cloud(*args, **kwargs):
            self.listener.cancel.set()
            return "выключи компьютер"
        self.recognizer.recognize_google.side_effect = cloud
        with patch.dict("sys.modules", {"speech_recognition": self.sr}):
            self.listener._run(False)
        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
