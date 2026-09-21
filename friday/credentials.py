"""Windows user-bound secrets. Never store credentials in settings or bundles."""
import os
import re
from pathlib import Path


class Secrets:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path(os.environ['LOCALAPPDATA']) / 'FridayAssistant' / 'secrets'

    def _path(self, name):
        if not re.fullmatch(r'[a-z0-9_-]{1,80}', name):
            raise ValueError('Некорректное имя секрета.')
        return self.root / (name + '.bin')

    def get(self, name):
        path = self._path(name)
        if not path.exists():
            return ''
        import win32crypt
        try:
            return win32crypt.CryptUnprotectData(path.read_bytes(), None, None, None, 1)[1].decode('utf-8')
        except Exception:
            raise ValueError('Не удалось расшифровать ключ. Введите его заново в этой учётной записи Windows.') from None

    def set(self, name, value):
        import win32crypt
        path = self._path(name)
        self.root.mkdir(parents=True, exist_ok=True)
        encrypted = win32crypt.CryptProtectData(value.encode('utf-8'), 'Friday', None, None, None, 1)
        temp = path.with_suffix('.tmp')
        temp.write_bytes(encrypted)
        os.replace(temp, path)

    def delete(self, name):
        self._path(name).unlink(missing_ok=True)


def openai_key():
    return Secrets().get('openai') or os.environ.get('OPENAI_API_KEY', '').strip()


def gemini_key():
    return Secrets().get('gemini') or os.environ.get('GEMINI_API_KEY', '').strip()

def groq_key():
    return Secrets().get('groq') or os.environ.get('GROQ_API_KEY', '').strip()
