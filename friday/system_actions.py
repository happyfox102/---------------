"""Windows brightness, power plans and local screenshots."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import time
import uuid


def brightness(value=None, delta=None):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    service = monitors = methods = monitor = args = result = None
    try:
        service = win32com.client.GetObject(r"winmgmts:\\.\root\wmi")
        monitors = list(service.ExecQuery("SELECT * FROM WmiMonitorBrightness WHERE Active=True"))
        methods = list(service.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods WHERE Active=True"))
        if not monitors or not methods:
            raise ValueError("Драйвер экрана не предоставляет управление яркостью. Используйте кнопки монитора или настройки Windows.")
        current = int(monitors[0].CurrentBrightness)
        if value is None and delta is None:
            return current
        level = max(0, min(100, int(value if value is not None else current + delta)))
        for monitor in methods:
            args = monitor.Methods_("WmiSetBrightness").InParameters.SpawnInstance_()
            args.Properties_("Timeout").Value = 0
            args.Properties_("Brightness").Value = level
            result = monitor.ExecMethod_("WmiSetBrightness", args)
            if result is not None and int(getattr(result, "ReturnValue", 0)) != 0:
                raise ValueError("Windows не удалось изменить яркость.")
        for _ in range(10):
            actual = int(list(service.ExecQuery("SELECT * FROM WmiMonitorBrightness WHERE Active=True"))[0].CurrentBrightness)
            if abs(actual - level) <= 1:
                return actual
            time.sleep(.1)
        raise ValueError("Драйвер не подтвердил изменение яркости.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Яркость недоступна: проверьте драйвер экрана и разрешения Windows.") from exc
    finally:
        result = args = monitor = None
        monitors = methods = service = None
        pythoncom.CoUninitialize()


PLANS = {"saver": "a1841308-3541-4fab-bc81-f71556f20b4a", "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e", "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"}
MODES = {"saver": "961cc777-2547-4f9d-8174-7d86181b8a7a", "balanced": "00000000-0000-0000-0000-000000000000", "performance": "ded574b5-45a0-4f42-8737-46345c09c238"}


def configured_modes(values=None):
    library = ctypes.windll.powrprof
    result = []
    for i, source in enumerate(("AC", "DC")):
        buffer = ctypes.create_string_buffer(16)
        getter = getattr(library, f"PowerGetUserConfigured{source}PowerMode")
        getter.argtypes = [ctypes.c_void_p]
        getter.restype = ctypes.c_ulong
        if values is not None:
            buffer.raw = uuid.UUID(values[i]).bytes_le
            setter = getattr(library, f"PowerSetUserConfigured{source}PowerMode")
            setter.argtypes = [ctypes.c_void_p]
            setter.restype = ctypes.c_ulong
            if setter(buffer):
                raise ValueError("Windows не разрешила изменить режим питания.")
        if getter(buffer):
            raise ValueError("Не удалось прочитать режим питания Windows.")
        result.append(str(uuid.UUID(bytes_le=buffer.raw)))
    return result


def powercfg(*args):
    exe = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/powercfg.exe")
    return subprocess.run([exe, *args], capture_output=True, timeout=15,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def active_plan():
    result = powercfg("/getactivescheme")
    match = re.search(rb"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", result.stdout)
    if result.returncode or not match:
        raise ValueError("Не удалось прочитать текущую схему питания.")
    return match[0].decode().lower()


def power_mode(mode):
    if hasattr(ctypes.windll.powrprof, "PowerSetUserConfiguredACPowerMode"):
        before = configured_modes()
        desired = [MODES[mode], MODES[mode]]
        try:
            if configured_modes(desired) != desired:
                raise ValueError("Windows не подтвердила смену режима питания.")
        except Exception:
            configured_modes(before)
            raise
        return "Выбран режим питания «" + {"saver": "Максимальная энергоэффективность", "balanced": "Сбалансированный", "performance": "Максимальная производительность"}[mode] + "»."
    guid = PLANS[mode]
    if powercfg("/setactive", guid).returncode or active_plan() != guid:
        raise ValueError("Windows не разрешила переключить схему питания.")
    return {"saver": "Включена схема питания «Экономия энергии».", "performance": "Включена схема питания «Высокая производительность».", "balanced": "Включена сбалансированная схема питания."}[mode]


def screenshot(path, active=False):
    import win32gui
    import win32ui
    import win32con
    from .qt import QtGui
    user = ctypes.windll.user32
    if active:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or win32gui.IsIconic(hwnd):
            raise ValueError("Нет активного окна для снимка.")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    else:
        left, top = user.GetSystemMetrics(76), user.GetSystemMetrics(77)
        right, bottom = left + user.GetSystemMetrics(78), top + user.GetSystemMetrics(79)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError("Не удалось определить размер экрана.")
    desktop = win32gui.GetDesktopWindow()
    handle = win32gui.GetWindowDC(desktop)
    source = win32ui.CreateDCFromHandle(handle)
    target = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(source, width, height)
        target.SelectObject(bitmap)
        target.BitBlt((0, 0), (width, height), source, (left, top), win32con.SRCCOPY | 0x40000000)  # CAPTUREBLT
        data = bitmap.GetBitmapBits(True)
        image = QtGui.QImage(data, width, height, width * 4, QtGui.QImage.Format.Format_RGB32).copy()
        if not image.save(str(path), "PNG"):
            raise ValueError("Не удалось сохранить скриншот.")
    finally:
        target.DeleteDC()
        source.DeleteDC()
        win32gui.ReleaseDC(desktop, handle)
        if bitmap.GetHandle():
            win32gui.DeleteObject(bitmap.GetHandle())
    return path
