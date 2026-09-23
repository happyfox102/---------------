"""Background filename index. File contents are never read."""
import os
from pathlib import Path
import threading
import time
import unicodedata


def key(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().replace("ё", "е").split()).strip(' «»"')


class FileIndex:
    SKIP = {"node_modules", "appdata", "windows", "venv", "__pycache__", "models", "runtime", "_internal", "$recycle.bin"}

    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.thread = None
        self.updated = 0
        self.roots = []
        self.entries = []
        self.ready = False
        self.error = ""
        cache = store.read("file-index.json", {})
        if isinstance(cache, dict) and cache.get("version") == 1:
            self.roots = cache.get("roots", [])
            self.entries = cache.get("entries", [])
            self.ready = True
            self.updated = time.monotonic()

    def refresh(self, force=False):
        roots = sorted({str(Path(p).expanduser().absolute()) for p in self.store.config.get("search_roots", []) if Path(p).is_dir()})
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            if roots != self.roots:
                self.ready = False
                self.entries = []
            if not force and self.ready and roots == self.roots and time.monotonic() - self.updated < 300:
                return
            self.thread = threading.Thread(target=self._scan, args=(roots,), daemon=True, name="filename-index")
            self.thread.start()

    def _scan(self, roots):
        entries, seen = [], set()
        try:
            for root in roots:
                stack = [Path(root)]
                while stack:
                    folder = stack.pop()
                    identity = os.path.normcase(str(folder))
                    if identity in seen:
                        continue
                    seen.add(identity)
                    if len(seen) % 100 == 0:
                        time.sleep(.02)
                    entries.append([str(folder), "folder", key(folder.name), key(folder.name)])
                    try:
                        with os.scandir(folder) as children:
                            for item in children:
                                try:
                                    if item.is_symlink() or (os.name == "nt" and os.path.isjunction(item.path)):
                                        continue
                                    if item.is_dir(follow_symlinks=False):
                                        if not item.name.startswith(".") and item.name.casefold() not in self.SKIP:
                                            stack.append(Path(item.path))
                                    elif item.is_file(follow_symlinks=False):
                                        entries.append([item.path, "file", key(item.name), key(Path(item.name).stem)])
                                except OSError:
                                    continue
                    except OSError:
                        continue
            self.store.write("file-index.json", {"version": 1, "roots": roots, "entries": entries})
            with self.lock:
                self.entries, self.roots = entries, roots
                self.updated, self.ready, self.error = time.monotonic(), True, ""
        except Exception as exc:
            with self.lock:
                self.error = str(exc)

    def find(self, query, kind):
        self.refresh()
        if not self.ready and self.thread:
            self.thread.join(1)
        with self.lock:
            if not self.ready:
                raise ValueError("Индекс ещё строится. Повторите команду через несколько секунд." if not self.error else "Не удалось построить индекс: " + self.error)
            entries = self.entries
        query = key(query)
        if not query:
            raise ValueError("Назовите файл или папку.")
        exact, partial = [], []
        for path, entry_kind, name, stem in entries:
            if kind != entry_kind or query not in name:
                continue
            candidate = Path(path)
            if not candidate.exists():
                continue
            (exact if query in (name, stem) else partial).append(candidate)
        return sorted(exact or partial, key=lambda p: (len(p.name), str(p).casefold()))
