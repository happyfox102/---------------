"""Scoped file operations with recoverable deletion."""
from pathlib import Path
import mimetypes
import os
import re
import shutil
import uuid


class FileTools:
    def __init__(self, store, index, cancel):
        self.store, self.index, self.cancel = store, index, cancel

    @property
    def roots(self):
        return [Path(p).expanduser().resolve() for p in self.store.config.get('search_roots', []) if Path(p).is_dir()] + [self.store.data.resolve()]

    def _check(self):
        if self.cancel.is_set(): raise RuntimeError('Задача остановлена.')

    def _path(self, value, existing=False):
        self._check()
        if not isinstance(value, str) or not value.strip() or len(value) > 4096 or '\x00' in value:
            raise ValueError('Некорректный путь.')
        path = Path(value).expanduser()
        if not path.is_absolute():
            matches = [root / path for root in self.roots]
            path = next((p for p in matches if p.exists()), matches[0])
        if any(':' in part for part in path.parts[1:]): raise ValueError('Потоки файлов не поддерживаются.')
        path = path.resolve(strict=False)
        if not any(path == root or root in path.parents for root in self.roots):
            raise ValueError('Путь находится вне разрешённых папок поиска.')
        if existing and not path.exists(): raise FileNotFoundError('Файл или папка не найдены.')
        return path

    def _writable(self, path):
        protected = [self.store.root.resolve(), self.store.data.resolve()]
        if any(path == root for root in self.roots) or any(path == p or path in p.parents for p in protected):
            raise ValueError('Нельзя изменять корневую папку поиска или папку приложения.')
        for name in ('friday', 'tools', 'tests', 'assets', 'runtime', 'models', 'build', 'dist', '.venv', '.git', '.codex', '.agents'):
            protected.append((self.store.root / name).resolve())
        protected += [(self.store.data / name).resolve() for name in ('backups', 'logs', 'browser-profile')]
        if any(path == p or p in path.parents for p in protected[2:]):
            raise ValueError('Служебные файлы приложения защищены.')
        if path.parent in (self.store.root.resolve(), self.store.data.resolve()) and path.suffix.lower() in ('.py', '.json', '.exe', '.bat', '.bin'):
            raise ValueError('Служебные файлы приложения защищены.')

    def _tree(self, path):
        if path.is_dir():
            for root, dirs, files in os.walk(path, followlinks=False):
                self._check()
                for name in dirs + files:
                    child = Path(root) / name
                    if child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction()):
                        raise ValueError('Папка содержит ссылки или junction. Обработайте их вручную.')

    def search(self, query):
        result = []
        for kind in ('file', 'folder'):
            for path in self.index.find(query, kind):
                try: result.append(str(self._path(str(path), True)))
                except (ValueError, FileNotFoundError): continue
                if len(result) >= 50: break
        return {'query': query, 'matches': result[:50], 'verified': True}

    def info(self, path):
        target = self._path(path, True); stat = target.stat()
        return {'path': str(target), 'name': target.name, 'type': 'folder' if target.is_dir() else mimetypes.guess_type(target.name)[0] or 'file',
                'size': stat.st_size if target.is_file() else None, 'verified': True}

    def create(self, path, kind='file', content=''):
        target = self._path(path); self._writable(target)
        folder = kind.casefold() in ('folder', 'папка', 'directory')
        if not folder and kind.casefold() not in ('file', 'файл', 'text', 'текст'):
            raise ValueError('Можно создать только текстовый файл или папку.')
        if not isinstance(content, str) or len(content) > 100000:
            raise ValueError('Текст ограничен 100000 символов.')
        if target.exists(): raise FileExistsError('Такой файл или папка уже существуют.')
        target.parent.mkdir(parents=True, exist_ok=True)
        if folder: target.mkdir()
        else:
            with target.open('x', encoding='utf-8') as stream: stream.write(content)
        self.index.refresh(force=True)
        return {'path': str(target), 'created': True, 'verified': target.is_dir() if folder else target.read_text(encoding='utf-8') == content}

    def _pair(self, source, destination):
        src = self._path(source, True); dst = self._path(destination)
        self._writable(src); self._writable(dst)
        if src == dst or src in dst.parents or dst in src.parents:
            raise ValueError('Нельзя помещать папку в себя или в родительскую папку с заменой.')
        if dst.exists(): raise FileExistsError('Путь назначения уже существует.')
        self._tree(src)
        return src, dst

    def _copy_file(self, source, destination):
        self._check()
        with open(source, 'rb') as source_file, open(destination, 'xb') as target_file:
            while block := source_file.read(1024 * 1024):
                self._check(); target_file.write(block)
        shutil.copystat(source, destination)
        return str(destination)

    def copy(self, source, destination):
        src, dst = self._pair(source, destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir(): shutil.copytree(src, dst, copy_function=self._copy_file)
        else: self._copy_file(src, dst)
        self.index.refresh(force=True)
        return {'source': str(src), 'destination': str(dst), 'verified': dst.exists()}

    def move(self, source, destination):
        src, dst = self._pair(source, destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try: src.rename(dst)
        except OSError:
            raise ValueError('Перемещение не выполнено. Для другого диска сначала скопируйте и проверьте файлы.') from None
        self.index.refresh(force=True)
        return {'source': str(src), 'destination': str(dst), 'verified': dst.exists() and not src.exists()}

    def rename(self, path, name):
        src = self._path(path, True)
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in ('.', '..') or name.endswith((' ', '.')):
            raise ValueError('Некорректное имя файла.')
        if any(ch in name for ch in '<>:"/\\|?*\x00\n\r') or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I):
            raise ValueError('Имя запрещено в Windows.')
        result = self.move(str(src), str(src.with_name(name)))
        return {'old': result['source'], 'new': result['destination'], 'verified': result['verified']}

    def delete(self, path):
        target = self._path(path, True); self._writable(target); self._tree(target)
        recovery = self.store.data / 'backups' / ('deleted-' + uuid.uuid4().hex)
        recovery.mkdir()
        destination = recovery / target.name
        try: target.rename(destination)
        except OSError:
            recovery.rmdir()
            raise ValueError('Удаление не выполнено: не удалось переместить объект в папку восстановления.') from None
        (recovery / 'restore.txt').write_text('Исходный путь: ' + str(target), encoding='utf-8')
        self.index.refresh(force=True)
        return {'path': str(target), 'deleted': not target.exists(), 'recovery': str(destination),
                'verified': destination.exists() and not target.exists()}
