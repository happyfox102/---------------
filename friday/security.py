"""Visible, local PC-protection helpers for Friday.

This module intentionally does not run covertly: monitoring must be enabled by
the person at the computer, uses a persistent UI indicator and writes only to
the local data folder.
"""
from __future__ import annotations

import ctypes
import json
import subprocess
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

    def event(self, kind: str, **data):
        item = {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind, **data}
        with self.events.open("a", encoding="utf-8") as file:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def defender_status(self) -> str:
        if not hasattr(ctypes, "windll"):
            return "Microsoft Defender доступен только в Windows."
        command = "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,QuickScanAge,FullScanAge | ConvertTo-Json -Compress"
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            values = json.loads(result.stdout or "{}")
            anti = "включён" if values.get("AntivirusEnabled") else "выключен"
            realtime = "включена" if values.get("RealTimeProtectionEnabled") else "выключена"
            return f"Microsoft Defender: антивирус {anti}, защита в реальном времени {realtime}."
        except Exception:
            return "Не удалось прочитать статус Microsoft Defender. Откройте «Безопасность Windows» и проверьте защиту вручную."

    def quick_scan(self) -> str:
        if not hasattr(ctypes, "windll"):
            return "Быстрая проверка Defender доступна только в Windows."
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", "Start-MpScan -ScanType QuickScan"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.event("defender_scan_started")
            return "Быстрая проверка Microsoft Defender запущена. Результат появится в «Безопасности Windows»."
        except OSError:
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
        self.known_pids = current
        for pid, name in started:
            data = {"pid": pid, "app": name, "window": self.active_window()}
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
        if screen.grabWindow(0).save(str(path), "PNG"):
            self.event("snapshot", file=path.name, window=self.active_window())
            return path
        return None

    def build_report(self) -> Path:
        rows = []
        try:
            rows = [json.loads(line) for line in self.events.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            pass
        started = [row for row in rows if row.get("kind") == "app_started"]
        shots = [row for row in rows if row.get("kind") == "snapshot"]
        report = self.root / ("report_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".md")
        lines = ["# Отчёт Защитника", "", f"Создан: {datetime.now():%d.%m.%Y %H:%M}", f"Событий: {len(rows)}", f"Снимков экрана: {len(shots)}", "", "## Запущенные приложения"]
        lines += [f"- {x['time']} — {x.get('app', 'неизвестно')}" + (" · отмечено родительским контролем" if x.get("restricted") else "") for x in started[-100:]] or ["- Нет записей."]
        lines += ["", "## Экран", f"Снимки сохранены в: {self.shots}", "", "Отчёт составлен локально. Экран и журнал не отправлялись в облачный ИИ."]
        report.write_text("\n".join(lines), encoding="utf-8")
        return report

    def lock_workstation(self) -> bool:
        if not hasattr(ctypes, "windll"):
            return False
        self.event("guard_armed", window=self.active_window())
        return bool(ctypes.windll.user32.LockWorkStation())
