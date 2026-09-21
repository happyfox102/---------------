"""Synthesize a test phrase into WAV and recognize it locally. No microphone/playback."""
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pythoncom
    import win32com.client
    import speech_recognition as sr
    from friday.speech import Listener
    from friday.storage import defaults
    from friday.engine import Engine
    folder = ROOT / "artifacts"
    folder.mkdir(exist_ok=True)
    path = folder / "speech-test.wav"
    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voices = voice.GetVoices()
        for i in range(voices.Count):
            if "419" in voices.Item(i).GetAttribute("Language"):
                voice.Voice = voices.Item(i)
                break
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(path), 3)
        try:
            voice.AudioOutputStream = stream
            voice.Speak("Пятница, который час?", 16)
        finally:
            stream.Close()
    finally:
        pythoncom.CoUninitialize()
    recognizer = sr.Recognizer()
    with sr.AudioFile(str(path)) as source:
        audio = recognizer.record(source)
    listener = Listener(lambda: defaults(ROOT), None, threading.Event(), lambda: False)
    text = listener.local(audio, defaults(ROOT))
    print("Recognized:", text)
    assert "пятница" in text.lower(), "Wake word was not recognized in synthesized test phrase"
    assert "час" in text.lower(), "Command was not recognized"
    print("Speech OK: Windows Russian TTS to WAV -> Vosk local recognition.")


if __name__ == "__main__":
    main()
