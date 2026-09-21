"""Only explicit, named Windows actions. Recognized text is never shell code."""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from .apps import AppCatalog, AppChoices

ALIASES = {
    "браузер": "browser", "chrome": "chrome", "хром": "chrome",
    "блокнот": "notepad", "калькулятор": "calc", "проводник": "explorer",
    "word": "word", "ворд": "word", "excel": "excel", "эксель": "excel",
    "telegram": "telegram", "телеграм": "telegram", "телеграмм": "telegram",
    "код": "code", "vs code": "code", "работу": "code",
    "youtube": "youtube", "ютуб": "youtube", "яндекс": "yandex",
    "диспетчер задач": "taskmgr", "диспетчера задач": "taskmgr", "панель управления": "control",
    "параметры": "settings", "настройки windows": "settings", "пейнт": "mspaint", "паинт": "mspaint",
    "ножницы": "snippingtool", "терминал": "wt", "командная строка": "cmd", "командную строку": "cmd",
    "дискорд": "discord", "стим": "steam", "спотифай": "spotify", "ватсап": "whatsapp",
    "ватсапп": "whatsapp", "зум": "zoom", "эдж": "msedge", "файрфокс": "firefox",
    "вс код": "code", "вижуал студио код": "code", "калькулятора": "calc",
}


def find_app(key: str, configured: dict) -> str | None:
    if key in configured and Path(configured[key]).is_file():
        return configured[key]
    exe = {"word": "WINWORD.EXE", "excel": "EXCEL.EXE", "code": "Code.exe",
           "telegram": "Telegram.exe", "chrome": "chrome.exe"}.get(key, key + ".exe")
    found = shutil.which(exe)
    if found:
        return found
    if os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}", 0, winreg.KEY_READ | view) as reg:
                        value = winreg.QueryValue(reg, None).strip('"')
                        if Path(value).is_file():
                            return value
                except OSError:
                    pass
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    roaming = Path(os.environ.get("APPDATA", str(Path.home())))
    candidates = {"telegram": roaming / "Telegram Desktop/Telegram.exe",
                  "code": local / "Programs/Microsoft VS Code/Code.exe",
                  "chrome": Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"}
    candidate = candidates.get(key)
    return str(candidate) if candidate and candidate.is_file() else None


class Windows:
    def __init__(self, store=None):
        self.catalog = AppCatalog(store)

    def warmup(self):
        self.catalog.refresh()

    def open_app(self, name: str, config: dict):
        key = ALIASES.get(name, name)
        urls = {"browser": "https://www.yandex.ru", "youtube": "https://www.youtube.com", "yandex": "https://www.yandex.ru"}
        if key in urls:
            webbrowser.open(urls[key])
            return
        if key == "settings":
            os.startfile("ms-settings:")
            return
        path = find_app(key, config.get("apps", {}))
        if not path:
            candidates = self.catalog.find(key)
            if not candidates and key != name:
                candidates = self.catalog.find(name)
            if len(candidates) > 1:
                raise AppChoices(candidates[:20])
            if candidates:
                self.catalog.launch(candidates[0])
                return
            raise ValueError(f"Программа «{name}» не найдена. Скажите «обнови список программ» или добавьте путь в настройках.")
        os.startfile(path)

    def brightness(self, value=None, delta=None):
        from .system_actions import brightness
        return brightness(value, delta)

    def power_mode(self, mode):
        from .system_actions import power_mode
        return power_mode(mode)

    def screenshot(self, path, active=False):
        from .system_actions import screenshot
        return screenshot(path, active)

    def volume(self, level: int):
        import comtypes
        from pycaw.pycaw import AudioUtilities
        comtypes.CoInitialize()
        try:
            endpoint = AudioUtilities.GetSpeakers().EndpointVolume
            endpoint.SetMasterVolumeLevelScalar(level / 100, None)
        finally:
            comtypes.CoUninitialize()

    def media(self, action: str):
        if action in ("mute", "unmute"):
            import comtypes
            from pycaw.pycaw import AudioUtilities
            comtypes.CoInitialize()
            try:
                AudioUtilities.GetSpeakers().EndpointVolume.SetMute(action == "mute", None)
            finally:
                comtypes.CoUninitialize()
            return
        key = {"pause": 0xB3, "next": 0xB0, "previous": 0xB1}[action]
        ctypes.windll.user32.keybd_event(key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key, 0, 2, 0)

    def power(self, action: str):
        if action == "shutdown":
            subprocess.run(["shutdown.exe", "/s", "/t", "30"], check=True, capture_output=True)
        elif action == "cancel_shutdown":
            subprocess.run(["shutdown.exe", "/a"], check=True, capture_output=True)
        elif action == "sleep":
            if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
                raise OSError("Windows не удалось перевести в сон.")

    def focus(self, title: str) -> str:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        matches = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        @callback_type
        def visit(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title.casefold() in buf.value.casefold():
                    matches.append((hwnd, buf.value))
            return True

        user32.EnumWindows(visit, 0)
        if not matches:
            raise ValueError("Открытое окно не найдено.")
        hwnd, name = matches[0]
        user32.ShowWindow(hwnd, 9)
        if not user32.SetForegroundWindow(hwnd):
            raise ValueError("Windows не разрешила переключить окно. Выберите его на панели задач.")
        return name

    def clipboard(self) -> str:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return ""
        finally:
            win32clipboard.CloseClipboard()

    def selected_text(self) -> str:
        # UI Automation reads selection without overwriting the user's clipboard.
        import comtypes.client
        from comtypes import CoInitialize, CoUninitialize
        CoInitialize()
        try:
            from comtypes.gen import UIAutomationClient as UIA
        except ImportError:
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as UIA
        try:
            automation = comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
            focused = automation.GetFocusedElement()
            pattern = focused.GetCurrentPattern(10014).QueryInterface(UIA.IUIAutomationTextPattern)
            ranges = pattern.GetSelection()
            return "\n".join(ranges.GetElement(i).GetText(-1) for i in range(ranges.Length))
        except Exception as exc:
            raise ValueError("Приложение не отдаёт выделение. Скопируйте текст и скажите «прочитай буфер обмена».") from exc
        finally:
            CoUninitialize()
