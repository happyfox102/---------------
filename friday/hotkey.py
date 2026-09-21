"""Global, non-consuming double Ctrl+Tab keyboard hook for Windows."""
import ctypes
from ctypes import wintypes
import os
import threading
import time

from .qt import QObject, Signal


class DoublePress:
    def __init__(self):
        self.down = False
        self.last = None

    def feed(self, pressed, ctrl, now):
        if not pressed:
            self.down = False
            return False
        if self.down:
            return False
        self.down = True
        if not ctrl:
            self.last = None
            return False
        if self.last is not None and 0 <= now - self.last <= .6:
            self.last = None
            return True
        self.last = now
        return False


class GlobalHotkey(QObject):
    activated = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread_id = None
        self.stopping = threading.Event()
        self.thread = None
        self.ready = threading.Event()

    def start(self):
        if os.name == "nt":
            self.thread = threading.Thread(target=self._run, daemon=True, name="friday-hotkey")
            self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x12, 0, 0)

    def _run(self):
        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class Key(ctypes.Structure):
            _fields_ = [("vk", wintypes.DWORD), ("scan", wintypes.DWORD), ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]

        user.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
        user.SetWindowsHookExW.restype = wintypes.HANDLE
        user.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user.CallNextHookEx.restype = ctypes.c_ssize_t
        user.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        kernel.GetModuleHandleW.restype = wintypes.HMODULE
        detector = DoublePress()

        @callback_type
        def callback(code, message, data):
            if code >= 0:
                key = ctypes.cast(data, ctypes.POINTER(Key)).contents
                if key.vk == 9 and not key.flags & 0x10:
                    ctrl = bool(user.GetAsyncKeyState(0x11) & 0x8000)
                    ctrl = ctrl and not (user.GetAsyncKeyState(0x10) & 0x8000 or user.GetAsyncKeyState(0x12) & 0x8000)
                    if detector.feed(message in (0x100, 0x104), ctrl, time.monotonic()):
                        self.activated.emit()
            return user.CallNextHookEx(None, code, message, data)

        msg = wintypes.MSG()
        user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self.thread_id = kernel.GetCurrentThreadId()
        hook = user.SetWindowsHookExW(13, callback, kernel.GetModuleHandleW(None), 0)
        if not hook:
            self.failed.emit("Не удалось включить глобальное Ctrl+Tab: " + str(ctypes.get_last_error()))
            return
        self.ready.set()
        try:
            while not self.stopping.is_set() and user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user.TranslateMessage(ctypes.byref(msg))
                user.DispatchMessageW(ctypes.byref(msg))
        finally:
            user.UnhookWindowsHookEx(hook)
            self.ready.clear()
            self.thread_id = None
