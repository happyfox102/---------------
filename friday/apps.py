"""Discover launchable applications from Windows and Start menu shortcuts."""
import os
from pathlib import Path
import threading
import time

from .file_index import key


class AppChoices(ValueError):
    def __init__(self, entries):
        self.entries = entries
        super().__init__("Найдено несколько программ.")


class AppCatalog:
    def __init__(self, store=None):
        self.store = store
        self.entries = []
        self.thread = None
        self.updated = 0
        self.error = ""
        self.lock = threading.Lock()
        if store:
            try:
                self.entries = store.read("apps-index.json", [])
            except RuntimeError:
                pass

    def refresh(self, force=False):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            if not force and time.monotonic() - self.updated < 300:
                return
            self.thread = threading.Thread(target=self._scan, daemon=True, name="friday-apps")
            self.thread.start()

    def _scan(self):
        import pythoncom
        import win32com.client
        import winreg
        pythoncom.CoInitialize()
        entries = []
        try:
            shell = win32com.client.Dispatch("Shell.Application")
            for item in shell.NameSpace("shell:AppsFolder").Items():
                appid = item.ExtendedProperty("System.AppUserModel.ID")
                if appid:
                    entries.append({"name": str(item.Name), "target": "shell:AppsFolder\\" + str(appid)})
            folders = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
                       Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
                       Path.home() / "Desktop", Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop"]
            for folder in folders:
                for shortcut in folder.rglob("*.lnk"):
                    if any(word in key(shortcut.stem) for word in ("uninstall", "удаление", "удалить")):
                        continue
                    entries.append({"name": shortcut.stem, "target": str(shortcut)})
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    try:
                        with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | view) as parent:
                            for i in range(winreg.QueryInfoKey(parent)[0]):
                                try:
                                    name = winreg.EnumKey(parent, i)
                                    with winreg.OpenKey(parent, name) as child:
                                        target = os.path.expandvars(winreg.QueryValue(child, None)).strip('"')
                                    if Path(target).is_file():
                                        entries.append({"name": Path(name).stem, "target": target})
                                except OSError:
                                    continue
                    except OSError:
                        continue
            # Prefer the Windows application identity when the same name has a shortcut.
            unique = {}
            for entry in entries:
                unique.setdefault(key(entry["name"]), entry)
            self.entries = sorted(unique.values(), key=lambda e: key(e["name"]))
            if self.store:
                self.store.write("apps-index.json", self.entries)
            self.updated = time.monotonic()
        except Exception as exc:
            self.error = str(exc)
        finally:
            item = shell = None
            pythoncom.CoUninitialize()

    def find(self, name):
        self.refresh()
        if not self.entries and self.thread:
            self.thread.join(4)
        query = key(name)
        exact = [e for e in self.entries if key(e["name"]) == query]
        if exact:
            return exact
        return [e for e in self.entries if query in key(e["name"])]

    @staticmethod
    def launch(entry):
        target = entry["target"]
        if not target.startswith("shell:AppsFolder\\") and not Path(target).is_file():
            raise ValueError("Программа удалена или перемещена. Скажите «обнови список программ».")
        os.startfile(target)
