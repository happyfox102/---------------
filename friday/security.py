"""Visible, local PC-protection helpers for Friday.

This module intentionally does not run covertly: monitoring must be enabled by
the person at the computer, uses a persistent UI indicator and writes only to
the local data folder.
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import psutil


class SecurityService:
    def __init__(self, store):
        self.store = store
        self.root = store.data / "security"
        self.shots = self.root / "snapshots"
        self.root.mkdir(exist_ok=True)
        self.shots.mkdir(exist_ok=True)
        self.events = self.root / "events.jsonl"
        self.known_pids: dict[int, str] = {}
        self.baseline = False
        self.lock = threading.RLock()

    def event(self, kind: str, **data):
        item = {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind, **data}
        with self.lock:
            with self.events.open("a", encoding="utf-8") as file:
                file.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def recent(self, limit=500):
        if not self.events.exists():
            return []
        # Read only the tail, even after months of monitoring.
        with self.lock, self.events.open('rb') as file:
            file.seek(0, 2)
            size = file.tell()
            file.seek(max(0, size - 512 * 1024))
            if size > 512 * 1024:
                file.readline()
            lines = deque(file, maxlen=limit)
        rows = []
        for line in lines:
            try:
                rows.append(json.loads(line))
            except (ValueError, UnicodeError):
                pass
        return rows

    def defender_status(self) -> str:
        if not hasattr(ctypes, "windll"):
            return "Microsoft Defender доступен только в Windows."
        command = "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,QuickScanAge,FullScanAge | ConvertTo-Json -Compress"
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode or not result.stdout.strip():
                return 'Статус Defender недоступен. Проверьте «Безопасность Windows».'
            values = json.loads(result.stdout)
            anti = "включён" if values.get("AntivirusEnabled") else "выключен"
            realtime = "включена" if values.get("RealTimeProtectionEnabled") else "выключена"
            return f"Microsoft Defender: антивирус {anti}, защита в реальном времени {realtime}."
        except Exception:
            return "Не удалось прочитать статус Microsoft Defender. Откройте «Безопасность Windows» и проверьте защиту вручную."

    def quick_scan(self) -> str:
        if not hasattr(ctypes, "windll"):
            return "Быстрая проверка Defender доступна только в Windows."
        try:
            self.event('defender_scan_requested', outcome='requested')
            result = subprocess.run(["powershell", "-NoProfile", "-Command", "$ErrorActionPreference='Stop'; Start-MpScan -ScanType QuickScan"],
                capture_output=True, timeout=3600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.event('defender_scan_finished', outcome='completed' if result.returncode == 0 else 'failed')
            return 'Команда проверки Defender завершена. Результаты угроз смотрите в «Безопасности Windows».' if result.returncode == 0 else 'Defender отклонил проверку. Проверьте права и состояние антивируса.'
        except (OSError, subprocess.TimeoutExpired):
            self.event('defender_scan_failed', outcome='failed')
            return "Не удалось запустить Defender. Откройте «Безопасность Windows» вручную."

    def active_window(self) -> str:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd).strip()[:300] or "без заголовка"
        except Exception:
            return "недоступно"

    def poll_processes(self, allowed: set[str] | None = None, parental=False):
        current = {}
        for proc in psutil.process_iter(("pid", "name")):
            try:
                current[int(proc.info["pid"])] = str(proc.info["name"] or "")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        started = [(pid, name) for pid, name in current.items() if pid not in self.known_pids]
        if not self.baseline:
            self.known_pids = current
            self.baseline = True
            return []
        for pid, name in self.known_pids.items():
            if pid not in current:
                self.event('app_closed', pid=pid, app=name, outcome='observed')
        self.known_pids = current
        window = self.active_window() if started else ''
        for pid, name in started:
            data = {"pid": pid, "app": name, "window": window, "outcome": "observed"}
            if parental and allowed and name.casefold() not in allowed:
                data["restricted"] = True
            self.event("app_started", **data)
        return started

    def screenshot(self):
        from .qt import QApplication
        screen = QApplication.primaryScreen()
        if screen is None:
            return None
        path = self.shots / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png")
        image = screen.grabWindow(0).toImage()
        window = self.active_window()
        if image.isNull():
            return None
        def save():
            if image.save(str(path), 'PNG'):
                self.event('snapshot', file=path.name, window=window, outcome='completed')
        threading.Thread(target=save, daemon=True, name='security-snapshot').start()
        return path
        return None

    def build_report(self) -> Path:
        rows = self.recent(1000)
        started = [row for row in rows if row.get("kind") == "app_started"]
        shots = [row for row in rows if row.get("kind") == "snapshot"]
        report = self.root / ("report_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".md")
        lines = ["# Отчёт Защитника", "", f"Создан: {datetime.now():%d.%m.%Y %H:%M}", f"Событий: {len(rows)}", f"Снимков экрана: {len(shots)}", "", "## Запущенные приложения"]
        lines += [f"- {x['time']} — {x.get('app', 'неизвестно')}" + (" · отмечено родительским контролем" if x.get("restricted") else "") for x in started[-100:]] or ["- Нет записей."]
        lines += ["", "## Экран", f"Снимки сохранены в: {self.shots}", "", "Отчёт составлен локально. Экран и журнал не отправлялись в облачный ИИ."]
        lines += ['', '## Действия и результаты (последние 1000 событий)']
        lines += [f"- {x.get('time')}: {x.get('kind')} · {x.get('outcome', 'observed')} · {x.get('reason', x.get('app', ''))}" for x in rows]
        report.write_text("\n".join(lines), encoding="utf-8")
        return report

    def lock_workstation(self) -> bool:
        if not hasattr(ctypes, "windll"):
            return False
        result = bool(ctypes.windll.user32.LockWorkStation())
        self.event('guard_lock', outcome='requested' if result else 'failed',
                   reason='Windows приняла запрос блокировки' if result else 'Windows отклонила запрос')
        return result
