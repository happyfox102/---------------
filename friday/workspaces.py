"""User-authored routines: deterministic steps, editable triggers, no shell code."""
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
import uuid
import webbrowser


def phrase(text):
    return re.sub(r'[^\w\s]', '', text.casefold().replace('ё', 'е')).strip()


class Workspaces:
    ACTIONS = {'app': 'Программа', 'url': 'Сайт', 'folder': 'Папка', 'music': 'Музыка (ссылка)',
               'brightness': 'Яркость', 'volume': 'Громкость', 'power': 'Питание', 'wait': 'Пауза, секунд'}

    def __init__(self, engine):
        self.engine, self.store = engine, engine.store

    def profiles(self):
        return self.store.read('workspaces.json', [])

    @staticmethod
    def validate_step(step):
        if not isinstance(step, dict) or set(step) != {'action', 'value'}:
            raise ValueError('Неверная структура шага.')
        action, value = step['action'], step['value']
        if action not in Workspaces.ACTIONS or not isinstance(value, str) or not value.strip() or len(value) > 2048:
            raise ValueError('Укажите действие и значение шага.')
        if action in ('brightness', 'volume', 'wait'):
            if not value.isdigit() or not 0 <= int(value) <= (30 if action == 'wait' else 100):
                raise ValueError('Яркость и громкость: 0–100. Пауза: 0–30 секунд.')
        if action in ('url', 'music'):
            url = urlsplit(value)
            if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
                raise ValueError('Ссылка должна начинаться с https:// или http://, без логина и пароля.')
        if action == 'app' and (Path(value).is_absolute() or '/' in value or '\\' in value):
            if not Path(value).is_absolute() or Path(value).suffix.lower() != '.exe':
                raise ValueError('Укажите название установленной программы или полный путь к EXE, без аргументов.')
        if action == 'power' and value not in ('saver', 'balanced', 'performance'):
            raise ValueError('Питание: saver, balanced или performance.')
        return {'action': action, 'value': value.strip()}

    def save(self, name, triggers, steps, ident=None):
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError('Название сценария: 1–80 символов.')
        if not isinstance(triggers, list) or not 1 <= len(triggers) <= 8 or any(not isinstance(t,str) or not phrase(t) or len(t)>100 for t in triggers):
            raise ValueError('Добавьте от 1 до 8 фраз запуска, до 100 символов.')
        if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
            raise ValueError('Сценарий должен содержать 1–20 шагов.')
        steps = [self.validate_step(step) for step in steps]
        values = self.profiles(); ident = ident or uuid.uuid4().hex
        wanted = {phrase(t) for t in triggers}
        for p in values:
            if p['id'] != ident and wanted.intersection(phrase(t) for t in p['triggers']):
                raise ValueError('Такая фраза уже используется другим сценарием.')
        profile = {'id': ident, 'name': name.strip(), 'triggers': list(dict.fromkeys(t.strip() for t in triggers)), 'steps': steps}
        self.store.write('workspaces.json', [p for p in values if p['id'] != ident] + [profile])
        return profile

    def remove(self, ident):
        self.store.write('workspaces.json', [p for p in self.profiles() if p['id'] != ident])

    def match(self, text):
        query = phrase(text)
        return next((p for p in self.profiles() if query in {phrase(t) for t in p['triggers']} or query == phrase('запусти сценарий '+p['name'])), None)

    def run(self, profile):
        # Validate the complete stored plan before the first side effect.
        steps = profile.get('steps')
        if not isinstance(steps, list) or not 1 <= len(steps) <= 20: raise ValueError('Неверное число шагов.')
        steps = [self.validate_step(step) for step in steps]
        cancel = self.engine.operator.cancel; cancel.clear()
        receipts = []
        for index, step in enumerate(steps, 1):
            if cancel.is_set(): return 'Сценарий остановлен. Завершено шагов: '+str(len(receipts))+'.'
            action, value = step['action'], step['value']
            self.engine.operator.progress(f'{profile["name"]}: {index}/{len(steps)} · {self.ACTIONS[action]}')
            try:
                if action == 'app':
                    path = Path(value)
                    if path.is_absolute():
                        if not path.is_file(): raise ValueError('Программа не найдена по сохранённому пути.')
                        subprocess.Popen([str(path)], cwd=str(path.parent))
                    else: self.engine.windows.open_app(value, self.store.config)
                    receipt = 'Запуск программы запрошен: '+path.name
                elif action in ('url', 'music'):
                    if not webbrowser.open(value): raise ValueError('Браузер не принял ссылку.')
                    receipt = 'Открытие музыки запрошено; воспроизведение зависит от сайта.' if action == 'music' else 'Открытие сайта запрошено.'
                elif action == 'folder':
                    path = Path(value).expanduser().resolve()
                    if not path.is_dir(): raise ValueError('Папка не найдена.')
                    os.startfile(str(path)); receipt = 'Открытие папки запрошено: '+path.name
                elif action == 'brightness': receipt = 'Яркость: '+str(self.engine.windows.brightness(value=int(value)))+'%'
                elif action == 'volume': self.engine.windows.volume(int(value)); receipt = 'Громкость установлена: '+value+'%'
                elif action == 'power': self.engine.windows.power_mode(value); receipt = 'Режим питания запрошен: '+value
                else:
                    if cancel.wait(int(value)): return 'Сценарий остановлен во время паузы.'
                    receipt = 'Пауза завершена.'
                receipts.append(receipt)
            except Exception as exc:
                return f'Сценарий остановлен на шаге {index}. '+str(exc)+'\n'+'\n'.join(receipts)
        return profile['name']+':\n'+'\n'.join(receipts)

    @staticmethod
    def visible_apps():
        import win32gui, win32process, psutil
        results = {}; own = os.getpid()
        def visit(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd): return
            title = win32gui.GetWindowText(hwnd).strip()
            if not title: return
            try:
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                if pid == own: return
                path = psutil.Process(pid).exe()
                if Path(path).name.lower() in ('explorer.exe', 'applicationframehost.exe', 'shellexperiencehost.exe', 'textinputhost.exe'): return
                if path and Path(path).suffix.lower() == '.exe': results[path] = {'title': title, 'path': path}
            except (OSError, psutil.Error): pass
        win32gui.EnumWindows(visit, None)
        return list(results.values())[:60]
