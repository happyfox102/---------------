from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from .storage import ChatDatabase

from .qt import QObject, QTimer, Qt, Signal
from .qt import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from .qt import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter, QSystemTrayIcon,
    QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from .engine import Engine, HELP
from .speech import Listener, Speaker, available_voices
from .storage import Store
from .hotkey import GlobalHotkey
from .pc_panel import PCPanel

from .design import stylesheet, apply_theme, palette, glyph, button as style_button, LoadingBar, Appearance
from .guide import HelpPage, Tour
from .qt import QtCore as C, QtWidgets as W

STYLE = stylesheet({})


def icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#73dfc1"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 18, 18)
    painter.setBrush(QColor("#102720"))
    for i, h in enumerate((14, 28, 40, 28, 14)):
        painter.drawRoundedRect(12 + i * 9, (64 - h) // 2, 5, h, 2, 2)
    painter.end()
    return QIcon(pix)


class Bus(QObject):
    progress = Signal(str)
    feature = Signal(str)
    result = Signal(str)
    error = Signal(str)
    maintenance = Signal(object)


class Settings(QDialog):
    devicesFound = Signal(object, object)

    def __init__(self, store, parent):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Настройки Пятницы")
        self.resize(940, 760)
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        self.tabs = tabs
        outer.addWidget(tabs)
        audio = QWidget()
        form = QFormLayout(audio)
        form.setSpacing(14)
        self.backend = QComboBox()
        for name, value in (("Google — нужен интернет", "google"), ("Vosk — локально, быстро", "vosk"), ("Whisper — локально, точнее / требовательнее", "whisper")):
            self.backend.addItem(name, value)
        self.backend.setCurrentIndex(max(0, self.backend.findData(store.config["speech_backend"])))
        form.addRow("Распознавание", self.backend)
        self.mic = QComboBox()
        self.mic.addItem("Микрофон Windows по умолчанию", None)
        form.addRow("Микрофон", self.mic)
        self.voice = QComboBox()
        self.voice.addItem("Голос Windows (выберите ниже)", "")
        form.addRow("Голос озвучки", self.voice)
        self.devices_ready = False
        self.device_progress = LoadingBar()
        self.device_progress.loading(True, "Поиск устройств и голосов Windows")
        form.addRow(self.device_progress)
        self.mic.setEnabled(False); self.voice.setEnabled(False)
        self.devicesFound.connect(self.populate_devices)
        self.device_thread = threading.Thread(target=self.load_devices, daemon=True, name="settings-devices")
        self.device_thread.start()
        self.rate = QSpinBox()
        self.rate.setRange(75, 350)
        self.rate.setValue(store.config["speech_rate"])
        form.addRow("Темп речи", self.rate)
        self.vosk = QLineEdit(store.config["vosk_model"])
        form.addRow("Папка модели Vosk", self.vosk)
        self.whisper = QLineEdit(store.config["whisper_model"])
        form.addRow("Модель / папка Whisper", self.whisper)
        self.wake = QLineEdit(store.config["wake_word"])
        form.addRow("Слово активации", self.wake)
        note = QLabel("Vosk — без интернета. Google отправляет запись для распознавания.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        form.addRow(note)
        tabs.addTab(audio, glyph("mic"), "Голос")

        files = QWidget()
        form = QFormLayout(files)
        self.roots = QTextEdit()
        self.roots.setPlainText("\n".join(store.config["search_roots"]))
        self.roots.setMaximumHeight(110)
        form.addRow("Папки поиска\nпо одной на строку", self.roots)
        add = QPushButton("Добавить папку…")
        add.clicked.connect(self.add_root)
        form.addRow(add)
        self.apps = QTextEdit()
        self.apps.setPlainText(json.dumps(store.config["apps"], ensure_ascii=False, indent=2))
        self.apps.setPlaceholderText('{"telegram": "C:/Users/Имя/AppData/Roaming/Telegram Desktop/Telegram.exe"}')
        form.addRow("Приложения (JSON)", self.apps)
        form.addRow(QLabel("Ключи: word, excel, telegram, chrome, code или своё название.\nДля путей используйте / или двойной обратный слеш."))
        self.history = QCheckBox("Сохранять историю диалога на этом компьютере")
        self.history.setChecked(store.config.get("history", True))
        form.addRow(self.history)
        tabs.addTab(files, glyph("folder"), "Файлы")

        extra = QWidget()
        form = QFormLayout(extra)
        from .ai_settings import AISettings
        self.cloud = AISettings(store)
        form.addRow(self.cloud)
        self.scenarios = QTextEdit()
        self.scenarios.setMaximumHeight(80)
        self.scenarios.setPlainText(json.dumps(store.config["scenarios"], ensure_ascii=False, indent=2))
        form.addRow("Сценарии (JSON)", self.scenarios)
        form.addRow(QLabel("До 10 шагов: запуск приложений, таймеры, громкость."))
        self.ai_url = QLineEdit(store.config["ollama_url"])
        self.ai_model = QLineEdit(store.config["ollama_model"])
        self.ai_model.setPlaceholderText("Название модели, установленной в Ollama")
        form.addRow("Адрес Ollama", self.ai_url)
        form.addRow("Модель ИИ", self.ai_model)
        self.web_enabled = QCheckBox("Доступ к публичным сайтам")
        self.web_enabled.setChecked(store.config.get('web_enabled', True)); form.addRow(self.web_enabled)
        self.web_auto = QCheckBox("Искать актуальную информацию автоматически")
        self.web_auto.setChecked(store.config.get('web_auto', True)); form.addRow(self.web_auto)
        self.web_enabled.setToolTip("Поисковику передаётся запрос. Cookies, экран и локальные файлы не отправляются.")
        label = QLabel("ИИ получает вопросы и контекст диалога. Файлы и экран автоматически не отправляются.")
        label.setWordWrap(True)
        form.addRow(label)
        ai_scroll = QScrollArea(); ai_scroll.setWidgetResizable(True); ai_scroll.setWidget(extra)
        tabs.addTab(ai_scroll, glyph("chat"), "ИИ")
        self.appearance = Appearance(store.config)
        tabs.addTab(self.appearance, glyph("palette"), "Дизайн")
        self.help_page = HelpPage(self)
        tabs.addTab(self.help_page, glyph("help"), "Справка")
        chats = QWidget(); chat_form = QFormLayout(chats)
        self.chat_side = QComboBox(); self.chat_side.addItem('Слева', 'left'); self.chat_side.addItem('Справа', 'right'); self.chat_side.setCurrentIndex(max(0, self.chat_side.findData(store.config.get('chat_panel_side','left')))); chat_form.addRow('Расположение истории чатов', self.chat_side)
        chat_form.addRow(QLabel('История хранится локально в SQLite. Разделы создаются кнопкой плюс.'))
        tabs.addTab(chats, glyph('chat'), 'Чаты')
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def load_devices(self):
        microphones, voices = [], []
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            try:
                for i in range(pa.get_device_count()):
                    info = pa.get_device_info_by_index(i)
                    if info["maxInputChannels"] > 0:
                        microphones.append((i, info["name"]))
            finally:
                pa.terminate()
        except Exception:
            logging.exception("Microphone enumeration failed")
        try:
            voices = available_voices()
        except Exception:
            logging.exception("Voice enumeration failed")
        try:
            self.devicesFound.emit(microphones, voices)
        except RuntimeError:
            pass  # Dialog was destroyed while Windows enumerated devices.

    def populate_devices(self, microphones, voices):
        for value, name in microphones:
            self.mic.addItem(name, value)
        for value, name in voices:
            self.voice.addItem(name, value)
        for combo, value in ((self.mic, self.store.config['microphone']), (self.voice, self.store.config.get('voice_id', ''))):
            index = combo.findData(value)
            if index < 0:
                combo.addItem("Сохранённое устройство недоступно", value); index = combo.count()-1
            combo.setCurrentIndex(index); combo.setEnabled(True)
        self.devices_ready = True; self.device_progress.loading(False)

    def add_root(self):
        path = QFileDialog.getExistingDirectory(self, "Папка для поиска")
        if path:
            self.roots.append(path)

    def reject(self):
        apply_theme(QApplication.instance(), self.store.config)
        super().reject()

    def save(self):
        from pathlib import Path
        from urllib.parse import urlparse
        try:
            apps = json.loads(self.apps.toPlainText())
            scenarios = json.loads(self.scenarios.toPlainText())
            if not isinstance(apps, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in apps.items()):
                raise ValueError("Приложения: нужен объект JSON с названиями и путями.")
            if not isinstance(scenarios, dict) or not all(isinstance(k, str) and isinstance(v, list) and 1 <= len(v) <= 10 and all(isinstance(s, str) for s in v) for k, v in scenarios.items()):
                raise ValueError("Сценарии: нужен объект JSON со списками из 1–10 команд.")
            roots = [line.strip() for line in self.roots.toPlainText().splitlines() if line.strip()]
            if any(not Path(root).is_dir() for root in roots):
                raise ValueError("Одна из папок поиска не существует.")
            if not self.wake.text().strip():
                raise ValueError("Укажите слово активации.")
            url = urlparse(self.ai_url.text().strip())
            if url.scheme not in ("http", "https") or not url.hostname:
                raise ValueError("Укажите адрес Ollama, например http://127.0.0.1:11434.")
            config = self.store.config.copy()
            config.update(self.cloud.values())
            config.update(speech_backend=self.backend.currentData(), microphone=self.mic.currentData() if self.devices_ready else self.store.config["microphone"],
                          voice_id=self.voice.currentData() if self.devices_ready else self.store.config.get("voice_id", ""), speech_rate=self.rate.value(),
                          vosk_model=self.vosk.text().strip(), whisper_model=self.whisper.text().strip(),
                          wake_word=self.wake.text().strip().lower(), search_roots=roots, apps=apps,
                          scenarios=scenarios, ollama_url=self.ai_url.text().strip(), ollama_model=self.ai_model.text().strip(),
                          history=self.history.isChecked(), design=self.appearance.config(), chat_panel_side=self.chat_side.currentData(),
                          web_enabled=self.web_enabled.isChecked(), web_auto=self.web_auto.isChecked())
            self.cloud.save_secret()
            self.store.save_config(config)
            apply_theme(QApplication.instance(), config)
            if hasattr(self.parent(), "apply_design"):
                self.parent().apply_design()
            self.accept()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Проверьте настройки", str(exc))


class Window(QMainWindow):
    def __init__(self, store=None):
        super().__init__()
        self.store = store or Store()
        apply_theme(QApplication.instance(), self.store.config)
        self.tour = None
        self.engine = Engine(self.store)
        self.busy = threading.Event()
        self.bus = Bus()
        self.bus.progress.connect(lambda text: self.ai_state.setToolTip(text))
        self.engine.operator.progress = self.bus.progress.emit
        self.bus.feature.connect(self.feature_action)
        self.engine.ui_action = self.bus.feature.emit
        self.recording = None
        self.bus.result.connect(self.on_result)
        self.bus.error.connect(self.show_error)
        self.bus.maintenance.connect(self.reminder_result)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="friday-actions")
        self.speaker = Speaker(lambda: self.store.config, self.bus.error.emit)
        self.listener = Listener(lambda: self.store.config, self.speaker, self.busy, lambda: self.engine.expecting_answer)
        self.listener.signals.text.connect(self.voice_command)
        self.listener.signals.status.connect(self.voice_status)
        self.listener.signals.error.connect(self.show_error)
        self.listener.signals.finished.connect(self.listening_finished)
        self.listener.signals.ready.connect(self.microphone_ready)
        self.direct_listening = False
        self.mic_announced = False
        self.hotkey_requested = False
        self.background = False
        self.accept_voice = False
        self.quitting = False
        self.maintenance_pending = False
        self.history = self.store.read("history.json", [])[-100:] if self.store.config.get("history", True) else []
        self.chat_db = ChatDatabase(self.store.root)
        self.chat_name = 'Общая'
        db_rows = self.chat_db.current()
        if db_rows:
            self.chat_name = db_rows[0][1]
        self.setWindowTitle("Пятница • личный помощник")
        self.setWindowIcon(icon())
        self.engine.file_index.refresh()
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self.engine.windows.warmup()
        self.resize(1100, 790)
        self.setMinimumSize(840, 600)
        self.build()
        self.apply_design()
        self.setup_tray()
        self.hotkey = GlobalHotkey(self)
        self.hotkey.activated.connect(self.toggle_global_microphone)
        self.hotkey.failed.connect(self.show_error)
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self.hotkey.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.activity_timer = QTimer(self)
        self.activity_timer.timeout.connect(self.update_activity)
        self.activity_timer.start(200)
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.listen_once)
        QShortcut(QKeySequence("Escape"), self, activated=self.stop_audio)
        if not self.history:
            self.append("Пятница", "Привет. Напиши вопрос или включи микрофон.", save=False)
        self.refresh_panels()
        if not self.store.config.get("tour_seen") and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QTimer.singleShot(900, self.start_tour)

    def build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("Пятница")
        title.setObjectName("brand")
        header.addWidget(title)
        subtitle = QLabel("Личный помощник")
        subtitle.setObjectName("muted")
        header.addWidget(subtitle)
        header.addStretch()
        studio = QPushButton("● Запись")
        self.studio_button = studio
        style_button(studio, "camera", icon_only=True)
        studio.clicked.connect(lambda: self.feature_action("record_tab"))
        header.addWidget(studio)
        self.guide_button = QPushButton("Знакомство с Пятницей")
        style_button(self.guide_button, "bulb", icon_only=True)
        self.guide_button.clicked.connect(self.start_tour)
        header.addWidget(self.guide_button)
        self.settings_button = QPushButton("Настройки")
        style_button(self.settings_button, "settings", icon_only=True)
        self.settings_button.clicked.connect(self.settings)
        header.addWidget(self.settings_button)
        self.panel_button = QPushButton("Панель быстрых действий")
        style_button(self.panel_button, "folder", icon_only=True)
        self.panel_button.clicked.connect(self.toggle_panel)
        header.addWidget(self.panel_button)
        self.chat_search_button = QPushButton(); style_button(self.chat_search_button, 'search', icon_only=True); self.chat_search_button.setToolTip('История чатов'); self.chat_search_button.clicked.connect(self.toggle_chat_panel); header.addWidget(self.chat_search_button)
        self.new_chat_button = QPushButton(); style_button(self.new_chat_button, 'plus', icon_only=True); self.new_chat_button.setToolTip('Новый чат'); self.new_chat_button.clicked.connect(self.add_chat); header.addWidget(self.new_chat_button)
        self.voice_output = QCheckBox("Голос")
        self.voice_output.setToolTip("Озвучивать ответы")
        self.voice_output.setChecked(self.store.config["speak"])
        self.voice_output.toggled.connect(self.toggle_speak)
        header.addWidget(self.voice_output)
        outer.addLayout(header)
        self.status = QLabel("Готова • микрофон выключен")
        self.status.setObjectName("status")
        self.status.setAccessibleName("Состояние помощника")
        self.status.hide()
        state_row = QHBoxLayout(); state_row.setSpacing(6)
        self.state_dot = QLabel("●"); self.state_dot.setToolTip("Пятница готова"); self.state_dot.setObjectName("stateDot")
        self.mic_state = QPushButton(); style_button(self.mic_state, "mic", icon_only=True); self.mic_state.setToolTip("Микрофон выключен")
        self.mic_state.clicked.connect(self.toggle_global_microphone)
        self.speaker_state = QPushButton(); style_button(self.speaker_state, "speaker", icon_only=True); self.speaker_state.setToolTip("Озвучка включена" if self.store.config['speak'] else "Озвучка выключена")
        self.speaker_state.clicked.connect(lambda: self.toggle_speak(not self.store.config['speak']))
        self.vision_state = QPushButton(); style_button(self.vision_state, "vision", icon_only=True); self.vision_state.setToolTip("Screen Vision выключен")
        self.vision_state.setEnabled(True); self.vision_state.setToolTip('Screen Vision включается по запросу; постоянного захвата нет')
        self.vision_state.setToolTip('Прочитать текст с изображения · Windows OCR')
        self.vision_state.clicked.connect(self.read_image)
        self.ai_state = QPushButton(); style_button(self.ai_state, "ai", icon_only=True); self.ai_state.setToolTip("Локальный ИИ готов")
        self.ai_state.setToolTip('ИИ: '+self.store.config.get('ai_provider','ollama'))
        self.ai_state.clicked.connect(self.settings)
        for chip in (self.state_dot,self.mic_state,self.speaker_state,self.vision_state,self.ai_state): state_row.addWidget(chip)
        state_row.addStretch(); outer.addLayout(state_row)
        self.activity = LoadingBar(self)
        outer.addWidget(self.activity)
        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)
        left = QWidget()
        column = QVBoxLayout(left)
        column.setContentsMargins(0, 0, 10, 0)
        self.tabs = QTabWidget()
        self.chat_select = QComboBox(); self.chat_select.currentTextChanged.connect(self.switch_chat); self.chat_select.setVisible(False)
        self.dialogue = QTextBrowser()
        self.dialogue.setStyleSheet('QTextBrowser { font-size: 16px; padding: 12px; }')
        self.dialogue.setOpenExternalLinks(False)
        self.dialogue.anchorClicked.connect(lambda url: self.submit('открой ссылку '+url.toString()) if url.scheme() in ('http','https') else None)
        self.dialogue.setAccessibleName("История диалога")
        self.tabs.addTab(self.dialogue, glyph("chat"), "Диалог")
        self.chat_panel = QFrame(); self.chat_panel.setObjectName('chatHistoryPanel'); self.chat_panel.setStyleSheet('#chatHistoryPanel { background:#111923; border-right:1px solid #2b3746; } QListWidget { background:transparent; border:0; font-size:14px; padding:4px; } QLineEdit { background:#1b2430; border:1px solid #344252; border-radius:9px; padding:8px; }'); chat_layout=QVBoxLayout(self.chat_panel)
        self.chat_query=QLineEdit(); self.chat_query.setPlaceholderText('Поиск чатов'); self.chat_query.returnPressed.connect(self.search_chats); chat_layout.addWidget(self.chat_query)
        self.chat_list=W.QListWidget(); self.chat_list.itemClicked.connect(lambda item: self.switch_chat(item.text())); chat_layout.addWidget(self.chat_list,1)
        tools=QHBoxLayout(); new_btn=QPushButton(); style_button(new_btn,'plus',icon_only=True); new_btn.clicked.connect(self.add_chat); tools.addWidget(new_btn); remove_btn=QPushButton(); style_button(remove_btn,'trash',icon_only=True); remove_btn.clicked.connect(self.delete_chat); tools.addWidget(remove_btn); chat_layout.addLayout(tools)
        self.chat_panel.setVisible(False)
        self.refresh_chat_sections()
        self.draft = QTextEdit()
        self.draft.setReadOnly(True)
        self.draft.setPlaceholderText("Скажите «начни диктовку». Черновик сохраняется после каждой фразы.")
        self.tabs.addTab(self.draft, glyph("file"), "Черновик")
        commands = QTextBrowser()
        commands.setPlainText(HELP)
        self.tabs.addTab(commands, glyph("help"), "Команды")
        self.pc = PCPanel(self.store, self)
        self.pc.message.connect(self.feature_message)
        self.tabs.addTab(self.pc, glyph("pc"), "Мой ПК")
        from .vpn_panel import VPNPanel
        self.vpn = VPNPanel(self.store)
        self.tabs.addTab(self.vpn, glyph("globe"), "VPN")
        from .workspaces_ui import WorkspacesPanel
        self.workspaces = WorkspacesPanel(self.engine)
        self.workspaces.runRequested.connect(self.submit)
        self.tabs.addTab(self.workspaces, glyph('skills'), 'Сценарии')
        from .skills_ui import SkillsPage
        self.skills_page = SkillsPage(self, mine=True)
        self.tabs.addTab(self.skills_page, glyph("skills"), "Способности")
        self.market_page = SkillsPage(self)
        self.tabs.addTab(self.market_page, glyph("marketplace"), "Marketplace")
        self.chat_area = QSplitter(Qt.Orientation.Horizontal)
        if self.store.config.get('chat_panel_side','left') == 'right': self.chat_area.addWidget(self.tabs); self.chat_area.addWidget(self.chat_panel)
        else: self.chat_area.addWidget(self.chat_panel); self.chat_area.addWidget(self.tabs)
        self.chat_area.setStretchFactor(0, 0); self.chat_area.setStretchFactor(1, 1)
        self.chat_panel.setMinimumWidth(210); self.chat_panel.setMaximumWidth(300)
        column.addWidget(self.chat_area, 1)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Напишите команду или вопрос ИИ…")
        self.input.setAccessibleName("Команда помощнику")
        self.input.returnPressed.connect(self.send)
        row.addWidget(self.input, 1)
        self.send_button = QPushButton("Отправить")
        self.send_button.setObjectName("primary")
        style_button(self.send_button, "send", icon_only=True)
        self.send_button.clicked.connect(self.send)
        row.addWidget(self.send_button)
        column.addLayout(row)
        row = QHBoxLayout()
        self.mic_button = QPushButton("Говорить")
        self.mic_button.setToolTip("Записать одну фразу • Ctrl+Пробел в окне помощника")
        style_button(self.mic_button, "mic")
        self.mic_button.clicked.connect(self.listen_once)
        row.addWidget(self.mic_button)
        self.background_button = QPushButton("Включить «Пятница»")
        style_button(self.background_button, "radio", "По имени")
        self.background_button.clicked.connect(self.toggle_background)
        row.addWidget(self.background_button)
        stop = QPushButton("Стоп / Esc")
        stop.setToolTip("Выключить микрофон и остановить озвучку")
        style_button(stop, "stop", icon_only=True)
        stop.clicked.connect(self.stop_audio)
        row.addWidget(stop)
        column.addLayout(row)
        split.addWidget(left)
        right = QWidget()
        self.quick_panel = right
        right.setMinimumWidth(260)
        right.setMaximumWidth(350)
        side = QVBoxLayout(right)
        side.setContentsMargins(6, 0, 0, 0)
        self.speak = QCheckBox("Отвечать голосом")
        self.speak.setChecked(self.store.config["speak"])
        self.speak.toggled.connect(self.toggle_speak)
        side.addWidget(self.speak)
        for title, command in (("Заметки", "покажи заметки"), ("Напоминания", "покажи напоминания")):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, c=command: self.submit(c))
            style_button(button, "clock" if command == "?????? ???????????" else "file")
            side.addWidget(button)
        select = QPushButton("Выбрать Excel…")
        select.clicked.connect(self.select_excel)
        side.addWidget(select)
        self.book_label = QLabel("Книга Excel не выбрана")
        self.book_label.setObjectName("muted")
        self.book_label.setWordWrap(True)
        side.addWidget(self.book_label)
        folder = QPushButton("Мои документы")
        folder.clicked.connect(lambda: os.startfile(self.store.data / "documents"))
        side.addWidget(folder)
        notes = QPushButton("Папка заметок")
        notes.clicked.connect(lambda: os.startfile(self.store.data / "notes"))
        side.addWidget(notes)
        side.addWidget(QLabel("Ближайшие напоминания"))
        self.reminder_label = QLabel("Нет активных напоминаний")
        self.reminder_label.setWordWrap(True)
        self.reminder_label.setObjectName("muted")
        side.addWidget(self.reminder_label)
        side.addStretch()
        hint = QLabel("Ctrl+Пробел — говорить\nEsc — остановить звук\n\n«Отмена» отменяет уточнение.\nНапоминания работают, пока приложение запущено.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        side.addWidget(hint)
        clear = QPushButton("Очистить историю")
        clear.clicked.connect(self.clear_history)
        side.addWidget(clear)
        tray = QPushButton("Свернуть в трей")
        tray.clicked.connect(self.hide_to_tray)
        side.addWidget(tray)
        for control, name in ((select,"file"),(folder,"folder"),(notes,"folder"),(clear,"trash"),(tray,"tray")):
            style_button(control, name)
        split.addWidget(right)
        split.setSizes([720, 300])

    def apply_design(self):
        apply_theme(QApplication.instance(), self.store.config)
        self.quick_panel.setVisible(palette(self.store.config)['sidebar'])
        self.dialogue.clear()
        for item in self.history:
            self.render_message(item['role'], item['text'])

    def toggle_panel(self):
        design = palette(self.store.config)
        config = dict(self.store.config, design=dict(self.store.config.get('design', {}), sidebar=not self.quick_panel.isVisible()))
        self.store.save_config(config)
        self.quick_panel.setVisible(config['design']['sidebar'])

    def start_tour(self):
        if self.quitting or self.tour is not None:
            return
        self.reveal()
        self.tour = Tour(self)

    def update_activity(self):
        if self.quitting:
            return
        index = self.engine.file_index.thread
        catalog = self.engine.windows.catalog.thread
        indexing = bool(index and index.is_alive() or catalog and catalog.is_alive())
        voice = self.accept_voice and any(word in self.status.text().lower() for word in ('настраиваю', 'распознаю', 'включаю'))
        self.activity.loading(self.busy.is_set() or indexing or voice, "Обработка команды" if self.busy.is_set() else "Подготовка микрофона" if voice else "Обновление каталогов")
        self.mic_state.setToolTip('Микрофон включён' if self.accept_voice else 'Микрофон выключен')
        self.speaker_state.setToolTip('Озвучка идёт' if self.speaker.busy.is_set() else 'Озвучка включена' if self.store.config['speak'] else 'Озвучка выключена')
        color=palette(self.store.config)['accent'] if self.busy.is_set() or self.accept_voice or self.speaker.busy.is_set() else palette(self.store.config)['muted']
        if self.state_dot.property('stateColor')!=color:
            self.state_dot.setProperty('stateColor',color); self.state_dot.setStyleSheet('color:'+color)
        self.state_dot.setToolTip(self.engine.operator.state if self.busy.is_set() else 'Готова')

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Пятница — микрофон выключен")
        menu = QMenu(self)
        for text, callback in (("Открыть Пятницу", self.reveal), ("Микрофон — Ctrl+Tab дважды", self.toggle_global_microphone), ("Выключить микрофон", self.stop_audio), ("Выход", self.quit)):
            action = QAction(text, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(self.reveal)
        self.tray.show()

    def reveal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray.showMessage("Пятница работает", "Напоминания активны. Для выхода используйте меню значка.")
        else:
            self.showMinimized()

    def feature_message(self, text):
        if not self.quitting:
            self.append("Пятница", text)
            self.status.setText(text)

    def feature_action(self, action):
        if action.startswith('workspaces'):
            self.tabs.setCurrentWidget(self.workspaces)
            if action == 'workspaces_capture': self.workspaces.capture()
            return
        if action.startswith('vpn'):
            self.tabs.setCurrentWidget(self.vpn)
            if action == 'vpn_connect': self.vpn.connect_selected()
            elif action == 'vpn_disconnect': self.vpn.disconnect_selected()
            elif action == 'vpn_status': self.vpn.refresh_status()
            return
        if action.startswith("record"):
            if self.recording is None:
                from .recording import RecordingPanel
                self.recording = RecordingPanel(self.store, self)
                self.recording.message.connect(self.feature_message)
                self.recording.activeChanged.connect(lambda active: self.tray.setToolTip("Пятница • запись идёт" if active else "Пятница • запись выключена"))
                self.tabs.addTab(self.recording, glyph("camera"), "Запись")
                apply_theme(QApplication.instance(), self.store.config)
            self.tabs.setCurrentWidget(self.recording)
            if action == "record_screen":
                self.recording.start(False)
            elif action == "record_camera":
                self.recording.start(True)
            elif action == "record_stop":
                self.recording.stop()
            elif action == "record_pause":
                self.recording.pause(False)
            elif action == "record_resume":
                self.recording.pause(True)
            return
        self.tabs.setCurrentWidget(self.pc)
        if action in self.pc.pages:
            self.pc.show_page(action)
        elif action == "scan":
            self.pc.show_page("disk"); self.pc.start_scan()
        else:
            self.pc.show_page("modes")
            if action in ("game", "work", "save"):
                self.pc.profile(action)
            elif action == "optimize":
                self.pc.optimize()
            elif action == "restore":
                self.pc.run_job(self.pc.optimizer.restore)

    def render_message(self, role, text):
        chunks=re.split(r'(https?://[^\s<>"\)]+)',text)
        content=''.join('<a href="'+html.escape(chunk,quote=True)+'">'+html.escape(chunk)+'</a>'
                        if i%2 else html.escape(chunk) for i,chunk in enumerate(chunks))
        stamp = datetime.now().strftime('%H:%M')
        align = 'right' if role == 'Вы' else 'left'
        bg = '#214d72' if role == 'Вы' else '#202936'
        side = 'right' if role == 'Вы' else 'left'
        self.dialogue.append(f'<table width="100%"><tr><td align="{side}"><div style="background:{bg}; border:1px solid #344252; border-radius:14px; padding:10px 14px; margin:8px; max-width:78%;"> <p style="font-weight:600;margin:0 0 4px">{html.escape(role)}</p><p style="white-space:pre-wrap;margin:0 0 4px; font-size:16px">{content.replace(chr(10), "<br>")}</p><p style="color:#9ca9b8;font-size:10px;margin:0">{stamp}</p></div></td></tr></table>')
        scroll = self.dialogue.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def append(self, role, text, save=True):
        self.render_message(role, text)
        if save:
            self.history.append({"role": role, "text": text, "time": datetime.now().isoformat()})
            self.history = self.history[-100:]
            if self.store.config.get("history", True):
                self.store.write("history.json", self.history)
            self.chat_db.add(self.chat_name, role, text, self.history[-1]['time'])

    def refresh_chat_sections(self):
        if not hasattr(self, 'chat_select'): return
        self.chat_select.blockSignals(True); self.chat_select.clear()
        for _, name, _ in self.chat_db.current(): self.chat_select.addItem(name)
        i=self.chat_select.findText(self.chat_name)
        if i>=0: self.chat_select.setCurrentIndex(i)
        self.chat_select.blockSignals(False)
        if hasattr(self,'chat_list'):
            self.chat_list.clear()
            for _, name, _ in self.chat_db.current(): self.chat_list.addItem(name)

    def toggle_chat_panel(self):
        self.chat_panel.setVisible(not self.chat_panel.isVisible())

    def switch_chat(self, name):
        if name: self.chat_name = name

    def add_chat(self):
        name, ok = W.QInputDialog.getText(self, 'Новый раздел', 'Название раздела:')
        if ok and name.strip():
            self.chat_db.add(name.strip(), 'system', '', datetime.now().isoformat()); self.chat_name=name.strip(); self.refresh_chat_sections()

    def delete_chat(self):
        if self.chat_name == 'Общая': return
        import sqlite3
        with sqlite3.connect(self.chat_db.path) as db: db.execute('DELETE FROM chats WHERE name=?',(self.chat_name,))
        self.chat_name='Общая'; self.refresh_chat_sections()

    def search_chats(self):
        query=self.chat_query.text().strip()
        if not query: return
        rows=self.chat_db.search(query); self.dialogue.clear()
        for name, role, text, created in reversed(rows): self.render_message(role + ' · ' + name, text)

    def send(self):
        text = self.input.text().strip()
        if text and not self.busy.is_set():
            self.input.clear()
            self.submit(text)

    def submit(self, text):
        if text.casefold().strip(' .!') in ('остановись','останови задачу','стоп задача','пятница остановись'):
            self.engine.operator.stop()
            self.ai_state.setToolTip('Останавливаю задачу'); return
        if self.busy.is_set():
            self.status.setText("Завершаю предыдущее действие…")
            return
        self.speaker.stop()
        self.busy.set()
        self.append("Вы", text)
        self.status.setText("Выполняю…")
        self.send_button.setEnabled(False)
        self.settings_button.setEnabled(False)
        future = self.executor.submit(self.engine.execute, text)
        def completed(future):
            try:
                text = future.result()
            except Exception as exc:
                logging.exception('Command failed in worker')
                text = 'Ошибка выполнения: ' + str(exc)
            self.bus.result.emit(text)
        future.add_done_callback(completed)

    def on_result(self, text):
        if self.quitting:
            return
        self.append("Пятница", text)
        self.send_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        self.refresh_panels()
        if not text.startswith("Черновик:"):
            self.speaker.say(text if len(text) < 1500 else "Ответ готов. Он показан в окне помощника.")
        if self.engine.dictation:
            self.tabs.setCurrentIndex(1)
        self.busy.clear()
        self.status.setText("Жду ответа…" if self.engine.pending else "Слушаю • Ctrl+Tab дважды — выключить" if self.direct_listening else "Готова • обращение включено" if self.background else "Готова • микрофон выключен")

    def voice_command(self, text):
        if self.accept_voice:
            self.submit(text)

    def voice_status(self, text):
        if self.accept_voice and not self.busy.is_set():
            self.status.setText(text)

    def show_error(self, text):
        if not self.quitting:
            self.append("Пятница", text)
            self.status.setText(text)

    def listen_once(self):
        if self.busy.is_set():
            return
        if self.listener.thread and self.listener.thread.is_alive():
            self.status.setText("Микрофон уже включён. Нажмите «Стоп» для отключения.")
            return
        self.speaker.stop()
        self.accept_voice = True
        self.background = False
        self.direct_listening = False
        if self.listener.start():
            self.mic_button.setEnabled(False)

    def toggle_background(self):
        if self.background:
            self.stop_audio()
            return
        if self.busy.is_set() or self.listener.thread and self.listener.thread.is_alive():
            return
        self.speaker.stop()
        self.accept_voice = True
        self.background = True
        self.direct_listening = False
        if self.listener.start(background=True):
            self.background_button.setText("Выключить «Пятница»")
            self.mic_button.setEnabled(False)
            self.tray.setToolTip("Пятница — обращение включено")

    def toggle_global_microphone(self):
        if self.quitting:
            return
        if self.accept_voice or self.hotkey_requested:
            self.stop_audio()
            return
        self.hotkey_requested = True
        self.start_global_microphone()

    def start_global_microphone(self):
        if not self.hotkey_requested or self.quitting:
            return
        # A cancelled capture may still be releasing the audio device.
        if self.listener.thread and self.listener.thread.is_alive():
            QTimer.singleShot(100, self.start_global_microphone)
            return
        self.speaker.stop()
        if self.listener.start(background=True, direct=True):
            self.hotkey_requested = False
            self.accept_voice = True
            self.background = True
            self.direct_listening = True
            self.mic_button.setEnabled(False)
            self.background_button.setText("Выключить микрофон")
            self.status.setText("Включаю микрофон…")

    def microphone_feedback(self, enabled):
        title = "Пятница — микрофон " + ("включён" if enabled else "выключен")
        self.tray.setToolTip(title)
        self.tray.showMessage(title,
            "Говорите команду или вопрос. Ctrl+Tab дважды — выключить." if enabled and self.direct_listening else
            "Скажите «Пятница», затем команду." if enabled and self.background else
            "Говорите команду или вопрос." if enabled else "Прослушивание остановлено. Ctrl+Tab дважды — включить.",
            QSystemTrayIcon.MessageIcon.Information, 4000)
        if os.name == "nt":
            def sound():
                try:
                    import winsound
                    for frequency in ((660, 990) if enabled else (990, 440)):
                        winsound.Beep(frequency, 70)
                except RuntimeError:
                    pass
            threading.Thread(target=sound, daemon=True, name="friday-mic-sound").start()

    def microphone_ready(self):
        if self.accept_voice and not self.quitting:
            self.mic_announced = True
            self.microphone_feedback(True)

    def stop_audio(self):
        self.engine.operator.stop()
        self.hotkey_requested = False
        self.accept_voice = False
        self.background = False
        self.direct_listening = False
        self.listener.stop()
        self.speaker.stop()
        self.background_button.setText("Включить «Пятница»")
        self.tray.setToolTip("Пятница — микрофон выключен")
        self.status.setText("Микрофон выключен • озвучка остановлена")
        if self.mic_announced:
            self.mic_announced = False
            self.microphone_feedback(False)

    def listening_finished(self):
        self.accept_voice = False
        self.background = False
        self.direct_listening = False
        if self.mic_announced:
            self.mic_announced = False
            self.microphone_feedback(False)
        self.mic_button.setEnabled(True)
        self.background_button.setText("Включить «Пятница»")
        self.tray.setToolTip("Пятница — микрофон выключен")

    def toggle_speak(self, checked):
        config = self.store.config.copy()
        config["speak"] = checked
        self.store.save_config(config)
        for control in (self.speak, self.voice_output):
            control.blockSignals(True); control.setChecked(checked); control.blockSignals(False)
        if not checked:
            self.speaker.stop()

    def settings(self):
        self.stop_audio()
        Settings(self.store, self).exec()
        provider = self.store.config.get('ai_provider', 'ollama')
        self.ai_state.setToolTip(provider + ' · ' + self.store.config.get('openai_model' if provider == 'openai' else 'ollama_model', ''))

    def read_image(self):
        if self.busy.is_set(): return
        path, _ = QFileDialog.getOpenFileName(self, 'Прочитать текст с изображения', str(self.store.data/'screenshots'), 'Изображения (*.png *.jpg *.jpeg)')
        if not path: return
        self.busy.set(); self.bus.progress.emit('Windows OCR читает изображение')
        def work():
            try:
                from .windows_ocr import read
                self.bus.result.emit(read(path).get('text') or 'Текст на изображении не найден.')
            except Exception as exc:
                self.bus.result.emit(str(exc))
        self.executor.submit(work)

    def select_excel(self):
        if self.busy.is_set():
            return
        self.stop_audio()
        path, _ = QFileDialog.getOpenFileName(self, "Выберите книгу (внешний файл будет скопирован)", str(self.store.data / "documents"), "Книга Excel (*.xlsx)")
        if path:
            self.busy.set()
            self.send_button.setEnabled(False)
            self.settings_button.setEnabled(False)
            def select():
                try:
                    return f"Рабочая книга: {self.engine.office.select(path)}\nКоманды изменяют активный лист."
                except Exception as exc:
                    return f"Не удалось выбрать книгу: {exc}"
            self.executor.submit(select).add_done_callback(lambda f: self.bus.result.emit(f.result()))

    def refresh_panels(self):
        self.draft.setPlainText(self.engine.draft)
        path = self.engine.office.path
        self.book_label.setText("Рабочая книга:\n" + path.name if path else "Книга Excel не выбрана")
        self.book_label.setToolTip(str(path) if path else "")
        reminders = self.engine.reminders()
        self.reminder_label.setText("\n\n".join(f"{datetime.fromtimestamp(x['due']):%d.%m %H:%M}\n{x['text']}" for x in reminders[:4]) or "Нет активных напоминаний")

    def tick(self):
        if self.quitting or self.maintenance_pending:
            return
        # Independent of slow AI requests: reminder storage has its own lock.
        try:
            for item in self.engine.due_reminders():
                text = "Напоминание: " + item["text"]
                self.append("Пятница", text)
                self.tray.showMessage("Пятница • напоминание", item["text"], QSystemTrayIcon.MessageIcon.Information, 10000)
                self.speaker.say(text)
            self.refresh_panels()
        except Exception:
            logging.exception("Reminder tick failed")

    def reminder_result(self, value):
        self.maintenance_pending = False

    def clear_history(self):
        self.history = []
        self.engine.chat.clear()
        self.store.write("history.json", [])
        self.dialogue.clear()

    def quit(self):
        self.close()

    def closeEvent(self, event):
        if self.recording and self.recording.active:
            self.recording.stop()
            self.status.setText("Сохраняю запись. После сохранения закройте приложение ещё раз.")
            event.ignore()
            return
        if self.pc.busy:
            self.status.setText("Дождитесь завершения настройки ПК.")
            event.ignore()
            return
        if self.busy.is_set():
            self.status.setText("Дождитесь завершения действия перед выходом. Можно свернуть окно в трей.")
            event.ignore()
            return
        self.quitting = True
        self.pc.close_services()
        self.hotkey.stop()
        self.timer.stop()
        self.activity_timer.stop()
        self.listener.stop()
        self.speaker.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.tray.hide()
        event.accept()
        QApplication.instance().quit()

