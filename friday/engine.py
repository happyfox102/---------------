from __future__ import annotations

import logging
import os
import re
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

from .office import Office, cell_address
from .storage import Store
from .windows import Windows
from .numbers import number
from .file_index import FileIndex
from .language import command_phrase
from .apps import AppChoices

HELP = """ПРОГРАММЫ  WINDOWS
МОЙ ПК  ЗАПСЬ
Открой мой ПК · Покажи нагрузку ПК · Открой характеристики ПК
Открой хранилище · Анализируй диск · Открой режимы ПК
Включи игровой режим · Включи рабочий режим · Включи энергосберегающий режим
Ускорь ПК · Верни настройки ПК
Открой запись экрана · Начни запись экрана · Начни запись экрана и камеры
Пауза записи · Продолжи запись · Останови запись

Открой браузер / Word / Excel / Telegram / блокнот
Открой диспетчер задач · Покажи список программ · Обнови список программ
Подними яркость · Спусти яркость на 20 · Установи яркость 50 процентов
Сделай скриншот · Сделай скриншот приложения
Включи энергосбережение · Включи производительность · Сбалансированное питание
Переключись на Word
Громкость 30 процентов · Пауза · Следующий трек · Выключи звук
Выключи компьютер · Отмена выключения · Спящий режим

ЗАМЕТК  ВРЕМЯ
Запомни купить молоко · Покажи заметки
Таймер на 5 минут
Через 20 минут напомни сделать перерыв
Напомни завтра в 10:30 позвонить
Покажи напоминания · Удали напоминание 1
Который час · Какая сегодня дата

ДКТОВКА  ДОКУМЕНТЫ
Начни диктовку → текст → Новый абзац / Удали последнее слово
Сохрани заметку / Сохрани диктовку в Word / Заверши диктовку
Создай Word Отчёт · Создай таблицу Бюджет · Создай txt План
Найди файл курсовая · Открой найденный файл 1
Открой папку код · Открой файл рейтинг · Запусти файл программа.exe
Обнови индекс файлов
Прочитай выделенное · Прочитай буфер обмена

EXCEL (активный лист выбранной книги)
Запиши 1500 в B3 · Прочитай B3
Добавить ячейку (пошаговый диалог)
Копируй A1 в B2 · Вырежи A1 в B2 · Объедини A1 и B1
Отмени изменение

ПОСК, СЦЕНАР  
Найди в интернете рецепт пасты
Прочитай страницу https://example.com
Браузер открой https://example.com
Браузер прочитай страницу · Браузер найди Learn more
Браузер нажми Learn more (после подтверждения)
Браузер введи Python в поле Search
Браузер закрой вкладку (после подтверждения)
Выполни задачу покажи процессы компьютера
Останови задачу
Начинаем учёбу (сценарии меняются в настройках)
Спроси  объясни этот текст ·  теперь короче
Переведи на английский добрый вечер (нужен настроенный )
Очисти контекст 

Отмена — отменить уточнение или подтверждение.
Список команд — показать эту справку.
"""


def normal(text: str) -> str:
    value = str(text).casefold().replace("ё", "е")
    # Remove emoji while preserving punctuation meaningful to URLs, filenames and numbers.
    value = ''.join(' ' if (ord(char) >= 0x1F000 or re.match(r'[\U0001F000-\U0001FAFF]', char)) else char for char in value)
    return re.sub(r"\s+", " ", value).strip(" .,!?:;")


def duration(text: str) -> float:
    text = normal(text)
    if text == "полчаса":
        return 1800
    matches = list(re.finditer(r"(.+?)\s*(секунд\w*|минут\w*|час\w*)(?:\s+и\s+|\s*|$)", text))
    if not matches or matches[-1].end() != len(text):
        raise ValueError("Укажите длительность: например 5 минут или 1 час 20 минут.")
    result = 0
    for match in matches:
        count = number(match[1])
        if count < 0:
            raise ValueError("Длительность не может быть отрицательной.")
        result += count * (3600 if match[2].startswith("час") else 60 if match[2].startswith("минут") else 1)
    if not 1 <= result <= 366 * 86400:
        raise ValueError("Допустимое время: от секунды до года.")
    return result


class Engine:
    def __init__(self, store: Store, windows=None, clock=time.time):
        self.store, self.windows, self.clock = store, windows or Windows(store), clock
        self.office = Office(store)
        self.pending = None
        self.dictation = False
        self.draft = store.read("draft.json", "")
        self.found: list[Path] = []
        self.chat = []
        self.screen_context = ''
        self.file_index = FileIndex(store)
        self.routing_ai = False
        self.ui_action = None
        from .operator import Operator
        self.operator = Operator(self)
        from .workspaces import Workspaces
        self.workspaces = Workspaces(self)

    @property
    def expecting_answer(self):
        return bool(self.pending and self.clock() <= self.pending["expires"]) or self.dictation or bool(self.operator.pending and time.monotonic() <= self.operator.pending['expires'])

    def execute(self, text: str) -> str:
        try:
            return self._execute(text.strip())
        except (ValueError, FileNotFoundError) as exc:
            return str(exc)
        except PermissionError:
            return "Нет доступа к файлу. Если таблица открыта в Excel, закройте её и повторите команду."
        except Exception:
            logging.exception("Command failed")
            return "Не удалось выполнить действие. Подробности записаны в data/logs/friday.log."

    def _execute(self, text: str) -> str:
        cmd = normal(text)
        if re.search(r'с какой\s+(?:ии|AI)|какой\s+провайдер|какая\s+модель', text, re.I):
            provider = self.store.config.get('ai_provider', 'ollama')
            names = {'gemini': 'Gemini', 'openai': 'OpenAI', 'ollama': 'Ollama'}
            model_key = {'gemini': 'gemini_model', 'openai': 'openai_model', 'ollama': 'ollama_model'}
            return f"Сейчас активен {names.get(provider, provider)}, модель: {self.store.config.get(model_key.get(provider, ''), 'не указана')}."
        wake = normal(self.store.config.get("wake_word", "пятница"))
        if cmd == wake:
            return "Слушаю. Назовите команду."
        if cmd.startswith(wake + " ") or cmd.startswith(wake + ","):
            text = re.sub(r"^" + re.escape(wake) + r"[\s,.:!]+", "", text, flags=re.I)
            cmd = normal(text)
        if not cmd:
            return "Введите или произнесите команду."
        if cmd in ("отмена", "отмени", "нет"):
            self.operator.stop()
            self.pending = None
            return "Действие отменено."
        if cmd in ("остановись", "останови задачу", "стоп задача"):
            self.operator.stop()
            self.pending=None
            return "Задача остановлена."
        if self.operator.pending:
            task=self.operator.pending
            if time.monotonic()>task['expires']:
                self.operator.pending=None
                return 'Время подтверждения истекло.'
            if cmd not in ('подтверждаю','да подтверждаю'):
                return 'Для выполнения скажите «подтверждаю», для отмены — «отмена».'
            self.operator.pending=None
            if task.get('computer_window'):
                import win32gui, win32process
                hwnd = win32gui.GetForegroundWindow()
                current = (hwnd, win32process.GetWindowThreadProcessId(hwnd)[1], win32gui.GetWindowText(hwnd))
                if current != task['computer_window']:
                    return 'Активное окно изменилось. Повторите команду и подтвердите голосом, оставив нужное окно активным.'
            if task.get('browser_page'):
                page=self.operator.browser.current()
                if (page['id'],page['url'])!=task['browser_page']:
                    return 'Страница изменилась после запроса подтверждения. Повторите команду.'
            result=self.operator.registry.call(task['name'],task['args'],task['allowed'],approved=True)
            return ('Действие выполнено и проверено.' if result['verified'] else result.get('result',{}).get('verification','Результат не проверен.')) if result['ok'] else result['error']
        if self.pending:
            return self.answer(text)
        if self.dictation:
            return self.dictate(text)
        routine = self.workspaces.match(text)
        if routine:
            return self.workspaces.run(routine)
        match=re.fullmatch(r'браузер открой\s+(https?://\S+)',text,re.I)
        if match:
            return self.operator.browser_command('browser.tab_open',{'url':match[1]})
        if cmd in ('браузер прочитай страницу','браузер текущая ссылка'):
            return self.operator.browser_command('browser.tab_read',{})
        if cmd=='браузер закрой вкладку':
            return self.operator.browser_command('browser.tab_close',{})
        match=re.fullmatch(r'браузер (найди|нажми)\s+(.+)',text,re.I)
        if match:
            return self.operator.browser_command('browser.find' if match[1].casefold()=='найди' else 'browser.click',{'text':match[2]})
        match=re.fullmatch(r'браузер введи\s+(.+?)\s+в поле\s+(.+)',text,re.I)
        if match:
            return self.operator.browser_command('browser.type',{'text':match[2],'value':match[1]})
        match=re.fullmatch(r'открой (?:источник|ссылку) (\d+)',cmd)
        if match:
            index=int(match[1])-1
            if not 0<=index<len(self.operator.sources):
                return 'Такого номера источника нет. Сначала выполните поиск.'
            return self.operator.browser_command('browser.open',{'url':self.operator.sources[index]['url']})
        match = re.match(r"(?:выполни задачу|агент)\s+(.+)", text, re.I | re.S)
        if match:
            task = match[1]
            if self.screen_context:
                task += '\n\nКонтекст предыдущего анализа экрана:\n' + self.screen_context[:8000]
            return self.operator.run(task)
        match = re.fullmatch(r"(?:прочитай (?:сайт|страницу)|изучи страницу)\s+(https?://\S+)", text, re.I)
        if match:
            return self.operator.research("Кратко изложи содержание страницы", url=match[1])
        match = re.fullmatch(r"открой (?:ссылку|сайт)\s+(https?://\S+)", text, re.I)
        if match:
            if not self.store.config.get('web_enabled',True):
                return 'Доступ к интернету выключен в настройках .'
            self.operator.cancel.clear()
            result = self.operator.registry.call('browser.open',{'url':match[1]})
            return result['result']['verification'] if result['ok'] else result['error']
        text = command_phrase(text)
        cmd = normal(text)
        features = {
            'открой сценарии': 'workspaces', 'настрой рабочее место': 'workspaces',
            'запомни рабочее место': 'workspaces_capture', 'научи сценарий': 'workspaces',
            'открой впн': 'vpn', 'открой vpn': 'vpn', 'включи впн': 'vpn_connect',
            'подключи впн': 'vpn_connect', 'включи vpn': 'vpn_connect',
            'выключи впн': 'vpn_disconnect', 'отключи впн': 'vpn_disconnect',
            'выключи vpn': 'vpn_disconnect', 'статус впн': 'vpn_status',
            "открой мой пк": "overview", "покажи нагрузку пк": "overview", "состояние пк": "overview",
            "открой характеристики пк": "hardware", "покажи характеристики компьютера": "hardware",
            "открой хранилище": "disk", "покажи хранилище": "disk", "анализируй диск": "scan",
            "открой режимы пк": "modes", "включи игровой режим": "game", "включи рабочий режим": "work",
            "включи энергосберегающий режим": "save", "ускорь пк": "optimize", "ускорь компьютер": "optimize",
            "оптимизируй пк": "optimize", "верни настройки пк": "restore",
            "открой запись экрана": "record_tab", "начни запись экрана": "record_screen", "включи запись экрана": "record_screen",
            "начни запись экрана и камеры": "record_camera", "включи запись экрана и камеры": "record_camera",
            "запиши экран с камерой": "record_camera", "останови запись": "record_stop", "заверши запись": "record_stop",
            "пауза записи": "record_pause", "продолжи запись": "record_resume"}
        if cmd in features:
            if self.ui_action:
                self.ui_action(features[cmd])
                return "Запрос передан. Состояние показано в соответствующей вкладке программы."
            return "Эта команда доступна в окне Пятницы."
        if cmd in ("покажи список программ", "какие программы установлены", "список программ"):
            self.windows.catalog.find("")
            return "\n".join(e["name"] for e in self.windows.catalog.entries) or "Каталог программ ещё загружается. Повторите запрос."
        if cmd == "обнови список программ":
            self.windows.catalog.refresh(force=True)
            return "Обновляю каталог программ в фоне."
        if cmd in ("сделай скриншот", "сделай скрин", "снимок экрана", "сделай снимок экрана", "сделай скриншот экрана", "сделай скриншот приложения", "сделай скриншот активного приложения", "сделай скриншот активного окна", "сделай скриншот окна"):
            folder = self.store.data / "screenshots"
            folder.mkdir(exist_ok=True)
            path = self.store.unique_path("screenshots", datetime.now().strftime("%Y-%m-%d %H-%M-%S"), ".png")
            self.windows.screenshot(path, active=any(w in cmd for w in ("приложения", "окна")))
            return f"Скриншот сохранён: {path}"
        match = re.fullmatch(r"(подними|повышай|повысь|увеличь|добавь|спусти|опусти|понизь|уменьши|убавь|снизь) яркость(?: (?:экрана|дисплея))?(?: на (.+?)(?: процент(?:а|ов)?|%)?)?", cmd)
        if match:
            amount = number(match[2]) if match[2] else 10
            if not 0 < amount <= 100:
                return "Укажите изменение яркости от 1 до 100 процентов."
            delta = amount if match[1] in ("подними", "повышай", "повысь", "увеличь", "добавь") else -amount
            return f"Яркость {self.windows.brightness(delta=delta)} процентов."
        match = re.fullmatch(r"(?:установи |сделай )?яркость(?: экрана)? (?:на )?(.+?)(?: процент(?:а|ов)?|%)?", cmd)
        if match:
            value = number(match[1])
            if not 0 <= value <= 100:
                return "Яркость должна быть от 0 до 100 процентов."
            return f"Яркость {self.windows.brightness(value=value)} процентов."
        power_modes = {
            "включи энергосбережение": "saver", "включи энергосбережения питания": "saver", "включи экономию энергии": "saver",
            "включи режим энергосбережения": "saver", "включи экономию заряда": "saver",
            "включи производительность": "performance", "включи высокую производительность": "performance", "включи режим производительности": "performance",
            "сбалансированное питание": "balanced", "включи сбалансированный режим": "balanced", "выключи энергосбережение": "balanced", "выключи производительность": "balanced"}
        if cmd in power_modes:
            return self.windows.power_mode(power_modes[cmd])
        if cmd in ("открой папку", "открой файл", "открой программу", "открой приложение"):
            kind = "folder" if "папку" in cmd else "file" if "файл" in cmd else "app"
            self.pending = {"kind": "open_name", "target": kind, "expires": self.clock() + 120}
            return "Какую папку открыть?" if kind == "folder" else "Какой файл открыть?" if kind == "file" else "Какую программу открыть?"
        if cmd in ("помощь", "список команд", "что ты умеешь"):
            return HELP
        if cmd in ("привет", "имя", "как тебя зовут"):
            return "Я Пятница. Помогу с программами, заметками, напоминаниями и документами."
        if cmd in ("который час", "сколько времени", "время"):
            return datetime.fromtimestamp(self.clock()).strftime("Сейчас %H:%M.")
        if cmd in ("какая сегодня дата", "дата"):
            return datetime.fromtimestamp(self.clock()).strftime("Сегодня %d.%m.%Y.")
        if cmd in ("выключи компьютер", "выключить пк", "отбой", "выключи пк"):
            return self.confirm("shutdown", None, "Выключить компьютер? Скажите «подтверждаю». После подтверждения будет 30 секунд для команды «отмена выключения».")
        if cmd in ("спящий режим", "спать", "усыпи компьютер"):
            return self.confirm("sleep", None, "Перевести компьютер в сон? Скажите «подтверждаю».")
        if cmd in ("отмена выключения", "отмени выключение"):
            self.windows.power("cancel_shutdown")
            return "Запрос на отмену выключения отправлен Windows."
        match = re.fullmatch(r"(?:громкость|установи громкость) (.+?)(?: процент(?:а|ов)?|%)?", cmd)
        if match:
            level = number(match[1])
            if not 0 <= level <= 100 or level != int(level):
                return "Громкость должна быть от 0 до 100."
            self.windows.volume(int(level))
            return f"Громкость {int(level)} процентов."
        media = {"пауза": "pause", "продолжи воспроизведение": "pause", "следующий трек": "next", "предыдущий трек": "previous", "выключи звук": "mute", "включи звук": "unmute"}
        if cmd in media:
            self.windows.media(media[cmd])
            return "Команда проигрывателю отправлена."
        match = re.fullmatch(r"переключись на (.+)", cmd)
        if match:
            name = {"ворд": "word", "эксель": "excel"}.get(match[1], match[1])
            return "Переключаюсь: " + self.windows.focus(name)
        if cmd in ("обнови индекс файлов", "обнови поиск файлов"):
            self.file_index.refresh(force=True)
            return "Обновляю индекс файлов и папок в фоне."
        match = re.fullmatch(r"(?:открой|открыть|запусти) (папку|файл) (.+)", cmd)
        if match:
            return self.open_named(match[2], "folder" if match[1] == "папку" else "file")
        match = re.fullmatch(r"(?:открой|открыть|запусти) найденный файл (\d+)", cmd)
        if match:
            index = int(match[1]) - 1
            if not 0 <= index < len(self.found):
                return "Такого номера нет. Сначала найдите файл."
            path = self.found[index]
            if path.suffix.lower() not in {".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg", ".mp3", ".mp4"}:
                return "Этот тип файла не открывается голосовой командой. Откройте его вручную."
            return self.confirm("open_file", str(path), f"Открыть {path}? Скажите «подтверждаю».")
        match = re.fullmatch(r"(?:открой|открыть|запусти) (.+)", cmd)
        if match:
            return self.open_program(match[1], text)
        match = re.match(r"(?:запомни|создай заметку|запиши заметку)\s+(.+)", text, re.I | re.S)
        if match:
            path = self.store.note(match[1])
            return f"Заметка сохранена: {path.name}."
        if cmd == "покажи заметки":
            paths = sorted((self.store.data / "notes").glob("*.txt"), reverse=True)[:10]
            return "\n\n".join(p.name + "\n" + p.read_text(encoding="utf-8")[:500] for p in paths) or "Пока нет заметок."
        match = re.fullmatch(r"таймер (?:на )?(.+)", cmd)
        if match:
            return self.add_reminder(self.clock() + duration(match[1]), "Таймер завершён")
        match = re.fullmatch(r"(?:через (.+?) напомни|напомни через (.+(?:секунд\w*|минут\w*|час\w*))) (.+)", cmd)
        if match:
            return self.add_reminder(self.clock() + duration(match[1] or match[2]), match[3])
        match = re.fullmatch(r"напомни (сегодня|завтра) в (\d{1,2})[:.](\d{2}) (.+)", cmd)
        if match:
            from datetime import timedelta
            when = datetime.fromtimestamp(self.clock()).replace(hour=int(match[2]), minute=int(match[3]), second=0, microsecond=0)
            if match[1] == "завтра":
                when += timedelta(days=1)
            if when.timestamp() <= self.clock():
                return "Это время уже прошло. Укажите будущее время."
            return self.add_reminder(when.timestamp(), match[4])
        if cmd == "покажи напоминания":
            items = self.reminders()
            return "\n".join(f"{i}. {datetime.fromtimestamp(x['due']):%d.%m %H:%M} — {x['text']}" for i, x in enumerate(items, 1)) or "Активных напоминаний нет."
        match = re.fullmatch(r"удали напоминание (\d+)", cmd)
        if match:
            with self.store.lock:
                items = self.reminders()
                index = int(match[1]) - 1
                if not 0 <= index < len(items):
                    return "Такого номера напоминания нет."
                items.pop(index)
                self.store.write("reminders.json", items)
            return "Напоминание удалено."
        if cmd in ("начни диктовку", "диктовка"):
            self.dictation = True
            return "Режим диктовки. Говорите текст. Для сохранения скажите «сохрани заметку» или «сохрани диктовку в Word»."
        match = re.match(r"создай (word|ворд|документ|excel|эксель|таблицу|txt|текстовый файл)(?:\s+(.+))?$", text, re.I)
        if match:
            kind = {"ворд": "word", "документ": "word", "эксель": "excel", "таблицу": "excel", "текстовый файл": "txt"}.get(match[1].lower(), match[1].lower())
            path = self.office.create(kind, match[2] or "Документ")
            return f"Создан файл: {path}" + ("\nКнига выбрана для голосовых команд." if kind == "excel" else "")
        match = re.match(r"(?:запиши|записать) (.+) в (.+)$", text, re.I)
        if match:
            self.office.change("write", match[2], match[1])
            return f"Записано в {cell_address(match[2])}. Книга сохранена."
        if cmd in ("добавить ячейку", "добавь ячейку", "заменить ячейку"):
            self.pending = {"kind": "cell", "expires": self.clock() + 120}
            return "В какую ячейку записать? Например B3."
        if cmd in ("прочитай выделенное", "прочитай буфер обмена"):
            value = self.windows.selected_text() if cmd == "прочитай выделенное" else self.windows.clipboard()
            return value[:6000] or "Текст не найден."
        match = re.fullmatch(r"прочитай (.+)", cmd)
        if match:
            return f"{cell_address(match[1])}: {self.office.read(match[1])}"
        match = re.fullmatch(r"(копируй|вырежи|объедини) (.+?) (?:в|и) (.+)", cmd)
        if match:
            self.office.change({"копируй": "copy", "вырежи": "cut", "объедини": "merge"}[match[1]], match[2], match[3])
            return "зменение сохранено. Можно сказать «отмени изменение»."
        if cmd in ("отмени изменение", "отменить изменение"):
            return self.office.undo()
        match = re.fullmatch(r"найди файл (.+)", cmd)
        if match:
            return self.search(match[1])
        match = re.fullmatch(r"найди в интернете (.+)", cmd)
        if match:
            return self.operator.research(match[1])
        if cmd in ("очисти контекст ии", "забудь разговор"):
            self.chat.clear()
            self.screen_context = ''
            return "Контекст  очищен."
        match = re.match(r"(?:спроси ии|ии)\s+(.+)", text, re.I | re.S)
        if match:
            return self.ask_ai(match[1])
        if cmd.startswith("переведи "):
            return self.ask_ai(text)
        scenarios = {normal(k): v for k, v in self.store.config.get("scenarios", {}).items()}
        if cmd in scenarios:
            return self.scenario(scenarios[cmd])
        if self.store.config.get('ai_provider') in ('openai', 'groq') or self.store.config.get("ollama_model"):
            if not self.routing_ai and re.search(r"\b(открой|запусти|включи|выключи|сделай|поставь|запечатлей|сфотографируй|нужен|нужна|ярк\w*|темно|светло|энерг\w*|скрин\w*)\b", cmd):
                routed = self.interpret_action(text)
                if routed:
                    return routed
            return self.ask_ai(text)
        return "Не нашла такую команду. Откройте «Команды» или начните вопрос словами «спроси »."

    def confirm(self, action, value, prompt):
        self.pending = {"kind": "confirm", "action": action, "value": value, "expires": self.clock() + 30}
        return prompt

    def answer(self, text):
        pending = self.pending
        if self.clock() > pending["expires"]:
            self.pending = None
            return "Время ожидания ответа истекло. Повторите команду."
        if pending["kind"] == "open_name":
            self.pending = None
            return self.open_program(text) if pending["target"] == "app" else self.open_named(text, pending["target"])
        if pending["kind"] == "app_choice":
            try:
                index = number(normal(text).removeprefix("номер "))
                if index != int(index) or not 1 <= index <= len(pending["entries"]):
                    raise ValueError()
            except ValueError:
                return "Назовите номер программы или скажите «отмена»."
            entry = pending["entries"][int(index) - 1]
            self.pending = None
            self.windows.catalog.launch(entry)
            return "Открываю: " + entry["name"]
        if pending["kind"] == "path_choice":
            try:
                index = number(re.sub(r"^(?:открой |номер )", "", normal(text)))
                if index != int(index) or not 1 <= index <= len(pending["paths"]):
                    raise ValueError()
            except ValueError:
                return "Назовите номер из списка или скажите «отмена»."
            self.pending = None
            return self.open_path(Path(pending["paths"][int(index) - 1]))
        if pending["kind"] == "confirm":
            if normal(text) not in ("подтверждаю", "да подтверждаю"):
                return "Для выполнения скажите «подтверждаю», для отмены — «отмена»."
            self.pending = None
            if pending["action"] == "open_file":
                os.startfile(pending["value"])
                return "Открываю выбранный файл."
            self.windows.power(pending["action"])
            return "Выключение запланировано через 30 секунд. Доступна команда «отмена выключения»." if pending["action"] == "shutdown" else "Команда перехода в сон отправлена."
        if pending["kind"] == "cell":
            address = cell_address(text)
            self.pending = {"kind": "value", "address": address, "expires": self.clock() + 120}
            return f"Что записать в {address}?"
        self.office.change("write", pending["address"], text)
        self.pending = None
        return "Значение записано. Книга сохранена."

    def dictate(self, text):
        cmd = normal(text)
        if cmd in ("заверши диктовку", "стоп диктовка"):
            self.dictation = False
            return "Диктовка остановлена. Черновик сохранён."
        if cmd in ("сохрани заметку", "сохрани диктовку", "сохрани диктовку в word", "сохрани диктовку в ворд"):
            if not self.draft.strip():
                return "Черновик пуст. Сначала продиктуйте текст."
            path = self.office.create("word", "Диктовка", self.draft) if "word" in cmd or "ворд" in cmd else self.store.note(self.draft)
            self.dictation = False
            self.draft = ""
            self.store.write("draft.json", self.draft)
            return f"Диктовка сохранена: {path}"
        if cmd == "новый абзац":
            self.draft = self.draft.rstrip() + "\n\n"
        elif cmd == "удали последнее слово":
            self.draft = re.sub(r"\S+\s*$", "", self.draft)
        elif cmd in ("точка", "запятая", "вопросительный знак", "восклицательный знак"):
            self.draft = self.draft.rstrip() + {"точка": ".", "запятая": ",", "вопросительный знак": "?", "восклицательный знак": "!"}[cmd]
        else:
            self.draft += (" " if self.draft and not self.draft[-1].isspace() else "") + text
        self.store.write("draft.json", self.draft)
        return "Черновик:\n" + self.draft

    def reminders(self):
        with self.store.lock:
            return sorted(self.store.read("reminders.json", []), key=lambda x: x["due"])

    def add_reminder(self, when, text):
        with self.store.lock:
            items = self.reminders()
            items.append({"id": uuid.uuid4().hex, "due": when, "text": text})
            self.store.write("reminders.json", items)
        return f"Напомню {datetime.fromtimestamp(when):%d.%m.%Y в %H:%M:%S}: {text}. Помощник должен оставаться запущенным."

    def due_reminders(self):
        with self.store.lock:
            items = self.reminders()
            due = [item for item in items if item["due"] <= self.clock()]
            if due:
                self.store.write("reminders.json", [item for item in items if item["due"] > self.clock()])
            return due

    def interpret_action(self, text):
        from .intent import interpret
        command = interpret(self.store, text)
        if not command:
            return None
        self.routing_ai = True
        try:
            result = self._execute(command)
            return "Поняла: «" + command + "».\n" + result
        finally:
            self.routing_ai = False

    def open_program(self, name, original=None):
        try:
            self.windows.open_app(name, self.store.config)
            return f"Открываю {name}."
        except AppChoices as exc:
            self.pending = {"kind": "app_choice", "entries": exc.entries, "expires": self.clock() + 120}
            return "Какую программу открыть? Назовите номер:\n" + "\n".join(f"{i}. {e['name']}" for i, e in enumerate(exc.entries, 1))
        except ValueError:
            if (self.store.config.get('ai_provider') in ('openai', 'groq') or self.store.config.get("ollama_model")) and not self.routing_ai:
                result = self.interpret_action(original or "открой " + name)
                if result:
                    return result
            raise

    def open_path(self, path):
        if not path.exists():
            return "Файл или папка больше не существует. Скажите «обнови индекс файлов»."
        if path.is_file() and path.suffix.casefold() in {".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".py", ".lnk", ".url", ".scr", ".com", ".hta", ".reg"}:
            return self.confirm("open_file", str(path), f"Запустить {path}? Скажите «подтверждаю».")
        os.startfile(str(path))
        return f"Открываю: {path}"

    def open_named(self, query, kind):
        paths = self.file_index.find(query, kind)
        if not paths:
            return "Не найдено. Проверьте папки поиска в настройках или скажите «обнови индекс файлов»."
        if len(paths) == 1:
            return self.open_path(paths[0])
        paths = paths[:20]
        self.pending = {"kind": "path_choice", "paths": [str(p) for p in paths], "expires": self.clock() + 120}
        return "Найдено несколько вариантов. Назовите номер или уточните название после отмены:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(paths, 1))

    def search(self, query):
        self.found = []
        deadline = time.monotonic() + 8
        visited = 0
        for root in self.store.config.get("search_roots", []):
            for current, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "AppData", "Windows", "venv") and not Path(current, d).is_symlink() and not Path(current, d).is_junction()]
                for name in files:
                    if normal(query) in normal(name):
                        self.found.append(Path(current, name))
                        if len(self.found) >= 20:
                            break
                visited += len(files)
                if len(self.found) >= 20 or time.monotonic() > deadline or visited > 100000:
                    break
            if len(self.found) >= 20 or time.monotonic() > deadline or visited > 100000:
                break
        return "\n".join(f"{i}. {p}" for i, p in enumerate(self.found, 1)) or "Файлы не найдены. Проверьте папки поиска в настройках."

    def scenario(self, steps):
        if not isinstance(steps, list) or not steps or len(steps) > 10:
            return "В сценарии должно быть от 1 до 10 команд."
        # Validate the whole scenario before executing any step.
        for step in steps:
            if not isinstance(step, str) or not re.fullmatch(r"(?:открой|запусти) [\w ]+|таймер (?:на )?[\w .,]+|громкость \d{1,3}(?: процентов)?", normal(step)) or "найденный файл" in normal(step):
                return "Сценарии поддерживают открытие приложений, таймеры и громкость. Другие действия выполняйте отдельно."
        return "\n".join(self.execute(step) for step in steps)

    def ask_ai(self, prompt):
        if re.search(r'экран|картинк|изображени|рабочем столе', prompt, re.I):
            try:
                snap = self.operator.vision.snapshot(False)
                ocr = self.operator.vision.ocr_read(snap['path'])
                text = ocr.get('text','') if isinstance(ocr, dict) else str(ocr)
                active = self.operator.vision.active()
                self.screen_context = ('Активное окно: ' + active.get('title','') + '\n' + text[:5000]).strip()
                if self.screen_context: prompt += '\nКонтекст текущего экрана:\n' + self.screen_context
            except Exception:
                pass
        if re.search(r'кто ты|что ты умеешь|что ты можешь|какие у тебя функции', prompt, re.I):
            return ('Я Пятница — агент для Windows. ИИ принимает вашу команду и планирует действия, '
                    'а мои инструменты выполняют их: запуск приложений и файлов, работа с папками, '
                    'браузер и поиск, системные настройки, скриншоты, громкость, яркость, режимы питания, '
                    'таймеры и сценарии. Я сообщаю результат только после проверки действия.')
        if self.store.config.get('web_auto',True) and re.search(r'\b(найди|поищи|проверь|свеж\w*|последн\w*|актуальн\w*|сегодня|сейчас|новост\w*|погод\w*|курс\w*|цен\w*)\b|https?://', prompt, re.I):
            match = re.search(r'https?://[^\s<>]+',prompt)
            return self.operator.research(prompt,url=match[0] if match else None)
        import requests
        config = self.store.config
        if config.get('ai_provider') == 'gemini':
            from .gemini_ai import complete
            try: answer = complete(config, [{'role':'system','content':'Ты Пятница. Отвечай кратко по-русски.'}] + self.chat[-12:] + [{'role':'user','content':prompt}], cancel=self.operator.cancel)
            except (ValueError, RuntimeError, TimeoutError) as exc: return str(exc)
            self.chat = (self.chat + [{'role':'user','content':prompt},{'role':'assistant','content':answer}])[-12:]
            return answer
        if config.get('ai_provider') in ('openai', 'groq'):
            messages = [{'role': 'system', 'content': 'Ты Пятница. Отвечай кратко по-русски. Это разговор: не утверждай, что выполнила действие на ПК.'}] + self.chat[-12:] + [{'role': 'user', 'content': prompt}]
            try:
                self.operator.cancel.clear()
                answer = self.operator.model(messages)
            except (ValueError, RuntimeError, TimeoutError) as exc:
                return str(exc)
            self.chat = (self.chat + [{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': answer}])[-12:]
            return answer
        model = config.get("ollama_model", "").strip()
        if not model:
            return " ещё не подключён. В настройках укажите адрес Ollama и название установленной модели."
        url = config.get("ollama_url", "").rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return "Проверьте адрес сервера  в настройках."
        messages = [{"role": "system", "content": "Ты Пятница, русскоязычный помощник. Отвечай ясно и кратко. Ты ведёшь разговор, но не можешь выполнять действия на компьютере. Не утверждай, что выполнила их."}] + self.chat[-12:] + [{"role": "user", "content": prompt}]
        try:
            payload = {"model": model, "messages": messages, "stream": False,
                       "options": {"num_predict": 384, "num_ctx": 4096, "temperature": 0.4}}
            try:
                response = requests.post(url + "/api/chat", json=payload, timeout=(5, 180))
            except requests.ConnectionError:
                from .ai import start_local_server
                if not start_local_server(url):
                    raise
                response = requests.post(url + "/api/chat", json=payload, timeout=(5, 180))
            response.raise_for_status()
            answer = response.json()["message"]["content"].strip()
            if not answer:
                return "Модель вернула пустой ответ. Попробуйте уточнить вопрос."
        except (requests.RequestException, ValueError, KeyError):
            return "Не удалось получить ответ . Проверьте, запущен ли Ollama и установлена ли указанная модель."
        self.chat.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])
        self.chat = self.chat[-12:]
        return answer

