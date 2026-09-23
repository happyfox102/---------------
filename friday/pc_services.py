"""PC metrics, cancellable disk analysis and reversible process optimization."""
import os
from pathlib import Path
import threading
import time
import re
import psutil

from .qt import QObject, Signal

BACKGROUND = {"chrome.exe", "msedge.exe", "firefox.exe", "discord.exe", "spotify.exe", "onedrive.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "teams.exe", "ms-teams.exe"}


def category(path):
    parts = {p.casefold() for p in path.parts}
    if parts & {"steamapps", "epic games", "epicgames", "games", "xboxgames"}:
        return "Игры"
    if parts & {"windows", "$recycle.bin", "system volume information"}:
        return "Система"
    if parts & {"program files", "program files (x86)", "windowsapps", "node_modules", ".venv", "appdata"}:
        return "Программы"
    ext = path.suffix.casefold()
    groups = {"Фото": {".jpg", ".jpeg", ".png", ".heic", ".webp", ".raw", ".gif"},
              "Видео": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
              "Музыка": {".mp3", ".wav", ".flac", ".aac"},
              "Документы": {".pdf", ".docx", ".doc", ".xlsx", ".txt", ".pptx", ".csv"},
              "Архивы": {".zip", ".7z", ".rar", ".iso"},
              "Программы": {".exe", ".dll", ".msi", ".sys"}}
    return next((name for name, extensions in groups.items() if ext in extensions), "Другие файлы")


def scan_disk(root, cancel, progress):
    totals, count, denied, seen = {}, 0, 0, set()
    stack, last = [Path(root)], time.monotonic()
    while stack and not cancel.is_set():
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if cancel.is_set():
                        break
                    try:
                        if entry.is_symlink() or os.path.isjunction(entry.path):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            stat = entry.stat(follow_symlinks=False)
                            identity = (stat.st_dev, stat.st_ino)
                            if stat.st_ino and identity in seen:
                                continue
                            seen.add(identity)
                            name = category(Path(entry.path))
                            totals[name] = totals.get(name, 0) + stat.st_size
                            count += 1
                    except OSError:
                        denied += 1
        except OSError:
            denied += 1
        if time.monotonic() - last > .8:
            progress(dict(totals), count, denied, False)
            last = time.monotonic()
    progress(totals, count, denied, not cancel.is_set())


def foreground_pid():
    import win32gui
    import win32process
    return win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1]


class Optimizer:
    def __init__(self, store):
        self.store = store
        self.saved = store.read("pc-restore.json", {})

    def lower(self, selected=None):
        active = foreground_pid()
        own = psutil.Process()
        protected = {own.pid, active, *[p.pid for p in own.parents()]}
        user = own.username()
        changed = 0
        for proc in psutil.process_iter(["pid", "name", "username", "create_time"]):
            try:
                if proc.pid in protected or proc.info["username"] != user or proc.info["name"].casefold() not in BACKGROUND:
                    continue
                if selected is not None and proc.pid not in selected:
                    continue
                old = proc.nice()
                if old in (psutil.IDLE_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS):
                    continue
                saved = self.saved.setdefault("processes", {})
                if str(proc.pid) not in saved or saved[str(proc.pid)][0] != proc.create_time():
                    saved[str(proc.pid)] = [proc.create_time(), int(old)]
                self.store.write("pc-restore.json", self.saved)
                proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                changed += 1
            except (psutil.Error, OSError):
                continue
        return f"Снижен приоритет фоновых процессов: {changed}. Активное окно и системные службы не затронуты."

    def profile(self, mode):
        from .system_actions import brightness, configured_modes, power_mode
        if "modes" not in self.saved:
            self.saved["modes"] = configured_modes()
            self.saved["brightness"] = brightness()
            self.store.write("pc-restore.json", self.saved)
        power = {"game": "performance", "work": "balanced", "save": "saver"}[mode]
        result = power_mode(power)
        try:
            result += f" Яркость: {brightness(value={'game': 100, 'work': 70, 'save': 40}[mode])}%."
        except ValueError as exc:
            result += " " + str(exc)
        if mode in ("game", "save"):
            result += " " + self.lower()
        elif mode == "work":
            for pid, (created, priority) in list(self.saved.get("processes", {}).items()):
                try:
                    proc = psutil.Process(int(pid))
                    if proc.create_time() == created:
                        proc.nice(priority)
                    del self.saved["processes"][pid]
                except psutil.NoSuchProcess:
                    del self.saved["processes"][pid]
                except psutil.Error:
                    continue
            self.store.write("pc-restore.json", self.saved)
        if mode == "game":
            result += " " + self.release_ai()
        return result

    def release_ai(self):
        import requests
        from urllib.parse import urlparse
        config = self.store.config
        url = config.get("ollama_url", "").rstrip("/")
        if urlparse(url).hostname not in ("localhost", "127.0.0.1") or not config.get("ollama_model"):
            return "Локальная модель ИИ не настроена."
        try:
            response = requests.post(url + "/api/generate", json={"model": config["ollama_model"], "keep_alive": 0, "stream": False}, timeout=10)
            response.raise_for_status()
            return "Локальному ИИ отправлена команда выгрузки из памяти. Следующий ответ потребует повторной загрузки модели."
        except requests.RequestException:
            return "Локальный ИИ не запущен или не ответил на запрос выгрузки."

    def close_selected(self, selected):
        import win32gui
        import win32process
        active = foreground_pid()
        targets = set()
        user = psutil.Process().username()
        for pid in selected:
            try:
                proc = psutil.Process(pid)
                if pid != active and proc.name().casefold() in BACKGROUND and proc.username() == user:
                    targets.add(pid)
            except psutil.Error:
                pass
        windows = []
        def visit(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] in targets:
                windows.append(hwnd)
        win32gui.EnumWindows(visit, None)
        for hwnd in windows:
            try:
                win32gui.PostMessage(hwnd, 0x10, 0, 0)  # WM_CLOSE, no forced termination
            except Exception:
                pass
        return f"Запрос закрытия отправлен окнам: {len(windows)}. Подтвердите сохранение документов в самих приложениях."

    def restore(self):
        from .system_actions import brightness, configured_modes
        errors = []
        for pid, (created, priority) in list(self.saved.get("processes", {}).items()):
            try:
                proc = psutil.Process(int(pid))
                if proc.create_time() == created:
                    proc.nice(priority)
                del self.saved["processes"][pid]
            except psutil.NoSuchProcess:
                del self.saved["processes"][pid]
            except psutil.Error:
                errors.append("приоритет " + pid)
        for field, action in (("modes", configured_modes), ("brightness", lambda x: brightness(value=x))):
            if field in self.saved:
                try:
                    action(self.saved[field])
                    del self.saved[field]
                except Exception:
                    errors.append(field)
        self.store.write("pc-restore.json", self.saved)
        return "Исходные настройки восстановлены." if not errors else "Не удалось восстановить: " + ", ".join(errors)


class Metrics(QObject):
    sample = Signal(dict)

    def __init__(self):
        super().__init__()
        self.cancel = threading.Event()
        self.thread = None
        self.visible = threading.Event()

    def start(self):
        self.visible.set()
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run, daemon=True, name="pc-metrics")
        self.thread.start()

    def run(self):
        import pythoncom
        import win32com.client
        import platform
        pythoncom.CoInitialize()
        service, hardware = None, platform.platform()
        try:
            service = win32com.client.GetObject(r"winmgmts:\\.\root\cimv2")
            cpus = [str(x.Name) for x in service.ExecQuery("SELECT Name FROM Win32_Processor")]
            gpus = [str(x.Name) for x in service.ExecQuery("SELECT Name FROM Win32_VideoController")]
            hardware = "\n".join(cpus + gpus + [platform.platform(), f"{psutil.cpu_count(logical=False)} ядер / {psutil.cpu_count()} потоков"])
        except Exception:
            pass
        psutil.cpu_percent()
        cache = {}
        previous_net = psutil.net_io_counters()
        previous_disk = psutil.disk_io_counters()
        previous_time = time.monotonic()
        try:
            while not self.cancel.wait(5):
                if not self.visible.is_set():
                    continue
                memory = psutil.virtual_memory()
                now = time.monotonic(); interval = max(.1, now - previous_time)
                net = psutil.net_io_counters(); disk = psutil.disk_io_counters()
                transfer = (net.bytes_recv - previous_net.bytes_recv) / interval
                disk_rate = (disk.read_bytes + disk.write_bytes - previous_disk.read_bytes - previous_disk.write_bytes) / interval if disk and previous_disk else 0
                previous_time, previous_net, previous_disk = now, net, disk
                battery = psutil.sensors_battery()
                frequency = psutil.cpu_freq()
                gpu = None
                if service:
                    try:
                        engines = {}
                        for row in service.ExecQuery("SELECT Name, UtilizationPercentage FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"):
                            name = re.sub(r"^pid_\d+_", "", str(row.Name))
                            engines[name] = engines.get(name, 0) + float(row.UtilizationPercentage)
                        values = list(engines.values())
                        if values:
                            gpu = min(100, max(values))
                    except Exception:
                        pass
                rows = []
                for proc in psutil.process_iter(["pid", "name", "memory_info"]):
                    try:
                        if proc.info["name"].casefold() in BACKGROUND:
                            obj = cache.setdefault(proc.pid, proc)
                            rows.append((proc.pid, proc.info["name"], obj.cpu_percent() / max(1, psutil.cpu_count()), proc.info["memory_info"].rss))
                    except psutil.Error:
                        continue
                cache = {pid: p for pid, p in cache.items() if psutil.pid_exists(pid)}
                self.sample.emit({"cpu": psutil.cpu_percent(), "ram": memory.percent, "used": memory.used, "total": memory.total,
                                  "gpu": gpu, "hardware": hardware, "download": transfer, "disk_rate": disk_rate,
                                  "battery": None if battery is None else [battery.percent, battery.power_plugged],
                                  "frequency": frequency.current if frequency else None,
                                  "processes": sorted(rows, key=lambda x: x[3], reverse=True)[:40]})
        finally:
            row = service = None
            pythoncom.CoUninitialize()
