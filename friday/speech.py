from __future__ import annotations

import io
import json
import logging
import os
import queue
import threading
import time
import unicodedata
from pathlib import Path

from .qt import QObject, Signal

from .engine import normal
from .language import command_phrase


def speech_text(value):
    """Remove emoji and visual-only markup before sending text to SAPI."""
    value = str(value)
    value = value.replace('```', '').replace('**', '').replace('__', '')
    result = []
    for char in value:
        category = unicodedata.category(char)
        if category in ('So', 'Sk') or 0x1F000 <= ord(char) <= 0x1FAFF or 0xFE00 <= ord(char) <= 0xFE0F:
            result.append(' ')
        else:
            result.append(char)
    return ' '.join(''.join(result).split()).strip()


def vosk_path(path):
    """Vosk's native Windows loader needs an ASCII path on some builds."""
    if os.name == "nt" and not str(path).isascii():
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetShortPathNameW(str(Path(path).resolve()), buffer, len(buffer)) and buffer.value.isascii():
            return buffer.value
        raise ValueError("Vosk не поддерживает этот путь с кириллицей. Выберите папку модели с латинским путём в настройках.")
    return str(path)


class SpeechSignals(QObject):
    ready = Signal()
    text = Signal(str)
    status = Signal(str)
    error = Signal(str)
    finished = Signal()


class Speaker:
    def __init__(self, config, on_error=lambda _: None):
        self.config = config
        self.on_error = on_error
        self.queue = queue.Queue()
        self.busy = threading.Event()
        self.interrupt = threading.Event()
        self.closed = threading.Event()
        self.epoch = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name="friday-speaker")
        self.thread.start()

    def say(self, text):
        text = speech_text(text)
        if self.config().get("speak", True) and text:
            self.epoch += 1
            self.busy.set()
            self.queue.put(text[:6000])

    def stop(self):
        self.epoch += 1
        self.interrupt.set()
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def close(self):
        self.closed.set()
        self.stop()

    def _run(self):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        voice = None
        try:
            while not self.closed.is_set():
                try:
                    text = self.queue.get(timeout=0.1)
                except queue.Empty:
                    self.busy.clear()
                    continue
                self.interrupt.clear()
                try:
                    if voice is None:
                        voice = win32com.client.Dispatch("SAPI.SpVoice")
                    config = self.config()
                    voices = voice.GetVoices()
                    selected = config.get("voice_id", "")
                    for i in range(voices.Count):
                        token = voices.Item(i)
                        if token.Id == selected or (not selected and "419" in token.GetAttribute("Language")):
                            voice.Voice = token
                            break
                    voice.Rate = max(-10, min(10, round((config.get("speech_rate", 175) - 175) / 20)))
                    voice.Speak(text, 1 | 16)  # async, plain text (not XML)
                    while not voice.WaitUntilDone(100):
                        if self.interrupt.is_set() or self.closed.is_set():
                            voice.Speak("", 2)
                            break
                except Exception:
                    logging.exception("Speech output failed")
                    self.on_error("Озвучка недоступна. Проверьте установленные голоса Windows.")
                finally:
                    if self.queue.empty():
                        self.busy.clear()
        finally:
            self.busy.clear()
            pythoncom.CoUninitialize()


def available_voices():
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        tokens = voice.GetVoices()
        return [(tokens.Item(i).Id, tokens.Item(i).GetDescription()) for i in range(tokens.Count)]
    finally:
        pythoncom.CoUninitialize()


class Listener:
    def __init__(self, config, speaker, busy, expecting):
        self.config, self.speaker, self.busy, self.expecting = config, speaker, busy, expecting
        self.signals = SpeechSignals()
        self.cancel = threading.Event()
        self.thread = None
        self.vosk = None
        self.vosk_path = None
        self.whisper = None
        self.whisper_key = None

    def start(self, background=False, direct=False):
        if self.thread and self.thread.is_alive():
            return False
        self.cancel.clear()
        self.thread = threading.Thread(target=self._run, args=(background, direct), daemon=True, name="friday-microphone")
        self.thread.start()
        return True

    def stop(self):
        self.cancel.set()

    def local(self, audio, config):
        from vosk import Model, KaldiRecognizer, SetLogLevel
        path = config["vosk_model"]
        if not Path(path).is_dir():
            raise ValueError("Локальная модель не установлена. Запустите install_offline.bat или выберите папку Vosk в настройках.")
        if self.vosk is None or self.vosk_path != path:
            SetLogLevel(-1)
            self.signals.status.emit("Загружаю локальную модель…")
            self.vosk = Model(vosk_path(path))
            self.vosk_path = path
        recognizer = KaldiRecognizer(self.vosk, 16000)
        recognizer.AcceptWaveform(audio.get_raw_data(convert_rate=16000, convert_width=2))
        return json.loads(recognizer.FinalResult()).get("text", "")

    def recognize(self, audio, recognizer, config):
        backend = config.get("speech_backend", "google")
        if backend == "vosk":
            text = self.local(audio, config)
            return self.command_cleanup(text)
        if backend == "whisper":
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ValueError("Для Whisper запустите install_whisper.bat. Затем выберите установленную модель в настройках.") from exc
            key = (config["whisper_model"], config.get("whisper_device", "cpu"))
            if self.whisper is None or key != self.whisper_key:
                self.signals.status.emit("Загружаю Whisper…")
                self.whisper = WhisperModel(key[0], device=key[1], compute_type="int8" if key[1] == "cpu" else "float16", local_files_only=True)
                self.whisper_key = key
            segments, _ = self.whisper.transcribe(io.BytesIO(audio.get_wav_data()), language="ru", vad_filter=True)
            return self.command_cleanup(" ".join(segment.text for segment in segments).strip())
        return self.command_cleanup(recognizer.recognize_google(audio, language="ru-RU"))

    @staticmethod
    def command_cleanup(text):
        text = command_phrase(normal(text or '').replace(',', ' '))
        replacements = {
            'пятница открой': 'открой', 'пятница запусти': 'запусти',
            'открой папочку': 'открой папку', 'открой файлик': 'открой файл',
            'включи энергосбережения': 'включи энергосбережение',
            'сделай снимок экрана': 'сделай скриншот', 'сделай снимок': 'сделай скриншот',
            'покажи мой пк': 'открой мой пк', 'открой компьютер': 'открой мой пк',
        }
        for source, target in replacements.items():
            if text == source or text.startswith(source + ' '):
                text = target + text[len(source):]
        return text

    def _run(self, background, direct=False):
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 0.7
        recognizer.operation_timeout = 12
        armed_until = 0
        try:
            config = self.config().copy()
            if background and not Path(config["vosk_model"]).is_dir():
                raise ValueError("Для фонового обращения нужна локальная модель Vosk. Запустите install_offline.bat.")
            self.signals.status.emit("Настраиваю микрофон…")
            with sr.Microphone(device_index=config.get("microphone")) as source:
                original_read = source.stream.read
                def cancellable_read(size):
                    if self.cancel.is_set():
                        raise InterruptedError("Microphone stopped")
                    return original_read(size)
                source.stream.read = cancellable_read
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                if self.cancel.is_set():
                    return
                self.signals.ready.emit()
                while not self.cancel.is_set():
                    if self.speaker.busy.is_set() or self.busy.is_set():
                        self.cancel.wait(0.1)
                        continue
                    config = self.config().copy()
                    self.signals.status.emit("Жду «Пятница»" if background and not direct and time.monotonic() > armed_until and not self.expecting() else "Слушаю…")
                    epoch = self.speaker.epoch
                    try:
                        audio = recognizer.listen(source, timeout=0.7 if background else 5, phrase_time_limit=12)
                    except sr.WaitTimeoutError:
                        if background:
                            continue
                        self.signals.status.emit("Речь не услышана. Нажмите кнопку и повторите.")
                        break
                    if self.cancel.is_set():
                        break
                    if epoch != self.speaker.epoch or self.speaker.busy.is_set() or self.busy.is_set():
                        continue
                    try:
                        wake = normal(config.get("wake_word", "пятница"))
                        waiting_for_wake = background and not direct and time.monotonic() > armed_until and not self.expecting()
                        if waiting_for_wake:
                            local_text = self.local(audio, config)
                            if self.cancel.is_set():
                                break
                            if epoch != self.speaker.epoch or self.busy.is_set():
                                continue
                            normalized = normal(local_text)
                            if normalized != wake and not normalized.startswith(wake + " "):
                                continue
                            armed_until = time.monotonic() + 20
                            if normalized == wake:
                                if not self.cancel.is_set():
                                    self.signals.text.emit(wake)
                                self.cancel.wait(0.3)
                                continue
                        if self.cancel.is_set():
                            break
                        self.signals.status.emit("Распознаю…")
                        text = self.recognize(audio, recognizer, config)
                        if self.cancel.is_set() or epoch != self.speaker.epoch:
                            continue
                        if text:
                            if background:
                                # Wake word has already been validated locally.
                                text = text.strip()
                            self.signals.text.emit(text)
                            armed_until = 0
                            self.cancel.wait(0.4)
                    except sr.UnknownValueError:
                        if not background:
                            self.signals.error.emit("Не удалось разобрать речь. Попробуйте ещё раз.")
                    except sr.RequestError:
                        self.signals.error.emit("Сервис распознавания недоступен. Проверьте интернет или выберите локальный Vosk.")
                        break
                    if not background:
                        break
        except Exception as exc:
            if self.cancel.is_set():
                return
            logging.exception("Microphone or recognition failed")
            message = str(exc) if isinstance(exc, ValueError) else "Не удалось включить распознавание. Проверьте микрофон, разрешения Windows и выбранную модель. Подробности — в журнале."
            self.signals.error.emit(message)
        finally:
            self.signals.finished.emit()
