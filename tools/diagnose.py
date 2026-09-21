"""Read-only dependency/device check. Does not record audio or run PC commands."""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    print("Python:", sys.version)
    failures = []
    for name in ("friday.qt", "speech_recognition", "pyaudio", "win32com.client", "pycaw.pycaw", "openpyxl", "docx", "vosk", "requests"):
        try:
            importlib.import_module(name)
            print("OK", name)
        except Exception as exc:
            failures.append(name)
            print("FAIL", name, str(exc))
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        try:
            inputs = [pa.get_device_info_by_index(i)["name"] for i in range(pa.get_device_count()) if pa.get_device_info_by_index(i)["maxInputChannels"] > 0]
            print("Input devices:", json.dumps(inputs, ensure_ascii=False))
        finally:
            pa.terminate()
        from friday.speech import available_voices
        print("Voices:", json.dumps(available_voices(), ensure_ascii=False))
    except Exception as exc:
        print("Device check:", str(exc))
    model = Path(__file__).resolve().parents[1] / "models/vosk-model-small-ru-0.22/am/final.mdl"
    print("Vosk model:", "installed" if model.exists() else "run install_offline.bat")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
