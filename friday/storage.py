from __future__ import annotations

import copy
import json
import os
import re
import threading
import sqlite3
from datetime import datetime
from pathlib import Path

from .paths import ROOT

class ChatDatabase:
    """Fast local SQLite history with searchable messages and chat sections."""
    def __init__(self, root):
        self.path = Path(root) / 'data' / 'chats.sqlite3'; self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY, name TEXT UNIQUE, tone TEXT DEFAULT "friendly", position INTEGER DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT, text TEXT, created TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS messages_text ON messages(text)')
            db.execute('INSERT OR IGNORE INTO chats(name,position) VALUES("Общая",0)')
    def current(self):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT id,name,tone FROM chats ORDER BY position,id').fetchall()
    def add(self, chat, role, text, created):
        with sqlite3.connect(self.path) as db:
            row=db.execute('SELECT id FROM chats WHERE name=?',(chat,)).fetchone(); cid=row[0] if row else db.execute('INSERT INTO chats(name) VALUES(?)',(chat,)).lastrowid
            db.execute('INSERT INTO messages(chat_id,role,text,created) VALUES(?,?,?,?)',(cid,role,text,created))
    def search(self, query):
        with sqlite3.connect(self.path) as db: return db.execute('SELECT c.name,m.role,m.text,m.created FROM messages m JOIN chats c ON c.id=m.chat_id WHERE m.text LIKE ? ORDER BY m.id DESC LIMIT 100',('%'+query+'%',)).fetchall()


def defaults(root: Path) -> dict:
    return {
        "speech_backend": "vosk" if (root / "models/vosk-model-small-ru-0.22").is_dir() else "google", "microphone": None, "speak": True,
        "voice_id": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\TokenEnums\\RHVoice\\Alan (RHVoice Plus)", "speech_rate": 175, "wake_word": "пятница",
        "vosk_model": str(root / "models" / "vosk-model-small-ru-0.22"),
        "whisper_model": "small", "whisper_device": "cpu",
        "search_roots": [str(p) for p in (Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads", Path(os.environ.get("OneDrive", str(Path.home()))) / "Desktop", root / "data/documents", root / "data/notes") if p.is_dir()],
        "apps": {}, "scenarios": {"начинаем учебу": ["открой браузер", "таймер на 25 минут"]},
        "ollama_url": "http://127.0.0.1:11435", "ollama_model": "qwen3:4b-instruct-2507-q4_K_M" if (root / "models/ollama/manifests/registry.ollama.ai/library/qwen3/4b-instruct-2507-q4_K_M").is_file() else "",
        "history": True,
        "ai_provider": "ollama", "openai_model": "gpt-4.1-mini", "gemini_model": "gemini-flash-latest", "groq_model": "openai/gpt-oss-20b",
        "web_enabled": True, "web_auto": True, "vision_model": "",
    }


class Store:
    def __init__(self, root: Path = ROOT):
        self.root = root.resolve()
        self.data = self.root / "data"
        self.data.mkdir(parents=True, exist_ok=True)
        for name in ("notes", "documents", "backups", "logs"):
            (self.data / name).mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.config = defaults(self.root)
        self.config.update(self.read("settings.json", {}))
        # Saved absolute model paths must survive moving the portable folder.
        if not Path(self.config["vosk_model"]).is_dir():
            bundled = self.root / "models/vosk-model-small-ru-0.22"
            if bundled.is_dir():
                self.config["vosk_model"] = str(bundled)

    def read(self, name: str, fallback):
        path = self.data / name
        if not path.exists():
            return copy.deepcopy(fallback)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise RuntimeError(f"Не удалось прочитать {path.name}. Сохраните копию файла и исправьте JSON: {exc}") from exc

    def write(self, name: str, value):
        with self.lock:
            path = self.data / name
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, path)

    def save_config(self, value):
        with self.lock:
            self.write("settings.json", value)
            self.config = copy.deepcopy(value)

    def unique_path(self, folder: str, title: str, suffix: str) -> Path:
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")[:90] or "Документ"
        if title.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
            title = "_" + title
        path = self.data / folder / (title + suffix)
        i = 2
        while path.exists():
            path = self.data / folder / f"{title} ({i}){suffix}"
            i += 1
        return path

    def note(self, text: str) -> Path:
        path = self.unique_path("notes", datetime.now().strftime("%Y-%m-%d %H-%M-%S"), ".txt")
        path.write_text(text, encoding="utf-8")
        return path
