"""VPN profile UI. Tunnel status is reported only from Windows, never guessed."""
from pathlib import Path
import threading
from .qt import QtWidgets as W, QtCore as C, Signal
from .design import LoadingBar, glyph
from .vpn import VPN


class VPNPanel(W.QWidget):
    done = Signal(object, str)

    def __init__(self, store):
        super().__init__()
        self.store, self.service = store, VPN(store)
        self.busy = False
        layout = W.QVBoxLayout(self)
        title = W.QLabel('VPN'); title.setObjectName('sectionTitle'); layout.addWidget(title)
        self.profiles = W.QComboBox(); self.profiles.currentIndexChanged.connect(self.selection)
        layout.addWidget(self.profiles)
        row = W.QHBoxLayout(); layout.addLayout(row)
        self.connect_button = W.QPushButton('Подключить'); self.connect_button.setIcon(glyph('bolt'))
        self.connect_button.clicked.connect(self.connect_selected); row.addWidget(self.connect_button)
        self.disconnect_button = W.QPushButton('Отключить'); self.disconnect_button.clicked.connect(self.disconnect_selected); row.addWidget(self.disconnect_button)
        refresh = W.QPushButton('Статус'); refresh.clicked.connect(self.refresh_status); row.addWidget(refresh)
        delete = W.QPushButton('Удалить'); delete.clicked.connect(self.remove); row.addWidget(delete)
        self.client_button = W.QPushButton('Выбрать клиент'); self.client_button.clicked.connect(self.choose_client); row.addWidget(self.client_button)
        self.status = W.QLabel('Добавьте профиль VPN.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.progress = LoadingBar(); layout.addWidget(self.progress)
        tabs = W.QTabWidget(); layout.addWidget(tabs)
        key_page = W.QWidget(); form = W.QFormLayout(key_page)
        self.key_name = W.QLineEdit(); self.key_name.setPlaceholderText('Мой VPN'); form.addRow('Название', self.key_name)
        self.key = W.QPlainTextEdit(); self.key.setMaximumHeight(130)
        self.key.setPlaceholderText('vpn://, vless://, vmess://, ss://, trojan://, happ://, https:// или конфигурация .conf/.json')
        form.addRow(self.key)
        import_row = W.QHBoxLayout(); form.addRow(import_row)
        read = W.QPushButton('Из файла'); read.clicked.connect(self.read_file); import_row.addWidget(read)
        save = W.QPushButton('Сохранить ключ'); save.clicked.connect(self.import_key); import_row.addWidget(save)
        info = W.QLabel('Ключ хранится зашифрованным. Для этих форматов туннель создаёт установленный AmneziaVPN или Happ. Передача ключа не означает подключение.')
        info.setWordWrap(True); form.addRow(info)
        tabs.addTab(key_page, 'Ключ / конфигурация')
        server_page = W.QWidget(); form = W.QFormLayout(server_page)
        self.server_name = W.QLineEdit(); form.addRow('Название', self.server_name)
        self.server = W.QLineEdit(); self.server.setPlaceholderText('IP или домен сервера'); form.addRow('Сервер', self.server)
        self.protocol = W.QComboBox(); self.protocol.addItem('IKEv2', 'Ikev2'); self.protocol.addItem('SSTP', 'Sstp'); form.addRow('Протокол', self.protocol)
        add = W.QPushButton('Добавить Windows VPN'); add.clicked.connect(self.add_server); form.addRow(add)
        info = W.QLabel('Протокол, логин и способ авторизации уточните у провайдера. Windows запросит данные при подключении. Это не настройка Amnezia по одному IP.')
        info.setWordWrap(True); form.addRow(info); tabs.addTab(server_page, 'Сервер Windows VPN')
        layout.addStretch()
        self.done.connect(self.finished)
        self.timer = C.QTimer(self); self.timer.setInterval(10000); self.timer.timeout.connect(self.poll)
        self.timer.start(); self.reload()

    def reload(self):
        selected = self.profiles.currentData(); ident = selected.get('id') if selected else None
        self.profiles.clear()
        for p in self.service.profiles():
            self.profiles.addItem(p['name'] + ' · ' + p['format'], p)
            if p['id'] == ident: self.profiles.setCurrentIndex(self.profiles.count() - 1)
        self.selection()

    def selection(self):
        p = self.profiles.currentData()
        external = bool(p and p['kind'] == 'external')
        self.connect_button.setText('Передать в ' + p['client'] if external else 'Подключить')
        self.connect_button.setEnabled(bool(p)); self.disconnect_button.setEnabled(bool(p and not external))
        self.client_button.setVisible(external)
        self.status.setText('Статус туннеля смотрите в ' + p['client'] + '. Пятница не проверяет его соединение.' if external else 'Статус ещё не проверен.' if p else 'Добавьте профиль VPN.')

    def run(self, callback):
        if self.busy: return
        self.busy = True; self.progress.loading(True)
        self.set_controls(False)
        def work():
            try: result, error = callback(), ''
            except Exception as exc:
                result, error = None, str(exc) if isinstance(exc, ValueError) else 'Операция VPN не выполнена. Проверьте настройки и права Windows.'
            try: self.done.emit(result, error)
            except RuntimeError: pass
        threading.Thread(target=work, daemon=True, name='vpn-operation').start()

    def set_controls(self, enabled):
        for child in self.findChildren(W.QPushButton): child.setEnabled(enabled)
        self.profiles.setEnabled(enabled)

    def finished(self, result, error):
        self.busy = False; self.progress.loading(False); self.set_controls(True); self.reload()
        if error: self.status.setText(error)
        elif isinstance(result, str): self.status.setText(result)
        elif isinstance(result, dict):
            p = self.profiles.currentData()
            if p and p['kind'] == 'windows':
                status = result.get(p['entry'])
                self.status.setText({'Connected': 'Подключено · Windows VPN', 'Disconnected': 'Отключено'}.get(status, 'Профиль отсутствует в Windows' if status is None else 'Состояние Windows: ' + str(status)))
        else: self.status.setText('Профиль сохранён.')

    def import_key(self):
        name, value = self.key_name.text(), self.key.toPlainText()
        if self.busy: return
        try:
            from .vpn import classify
            classify(value)
            if not name.strip() or len(name.strip()) > 60: raise ValueError('Введите название профиля до 60 символов.')
        except ValueError as exc:
            self.status.setText(str(exc)); return
        def save():
            self.service.import_key(name, value)
            return 'Ключ сохранён. Выберите профиль и передайте его в VPN-клиент.'
        self.run(save); self.key.clear()

    def read_file(self):
        filename, _ = W.QFileDialog.getOpenFileName(self, 'Конфигурация VPN', '', 'VPN (*.conf *.json *.txt)')
        if not filename: return
        try:
            path = Path(filename)
            if path.stat().st_size > 262144: raise ValueError('Файл больше 256 КБ.')
            self.key.setPlainText(path.read_text(encoding='utf-8-sig'))
            if not self.key_name.text(): self.key_name.setText(path.stem[:60])
        except (OSError, ValueError): self.status.setText('Не удалось прочитать конфигурацию UTF-8 до 256 КБ.')

    def add_server(self):
        args = self.server_name.text(), self.server.text(), self.protocol.currentData()
        def add():
            self.service.add_server(*args)
            return 'Профиль Windows создан. Выберите его и нажмите «Подключить».'
        self.run(add)

    def connect_selected(self):
        if self.busy: return
        p = self.profiles.currentData()
        if not p: return
        if p['kind'] == 'windows': self.run(lambda: self.service.connect(p)); return
        try:
            if not self.service.client_path(p): self.choose_client()
            if not self.service.client_path(p): return
            value = self.service.secrets.get('vpn-' + p['id'])
            if not value: raise ValueError('Ключ не найден в этой учётной записи Windows. Импортируйте его заново.')
            if p['file']:
                suffix = '.json' if p['format'] == 'JSON' else '.conf'
                filename, _ = W.QFileDialog.getSaveFileName(self, 'Экспорт для клиента: файл содержит секретные ключи', 'VPN' + suffix, 'VPN (*' + suffix + ')')
                if not filename: return
                Path(filename).write_text(value, encoding='utf-8')
                note = 'В клиенте выберите импорт из сохранённого файла. После импорта удалите экспорт с ключами.'
            else:
                answer = W.QMessageBox.question(self, 'Передать ключ', 'Ключ будет помещён в буфер обмена для импорта в ' + p['client'] + '. Продолжить?')
                if answer != W.QMessageBox.StandardButton.Yes: return
                clipboard = W.QApplication.clipboard(); clipboard.setText(value)
                C.QTimer.singleShot(60000, lambda: clipboard.clear() if clipboard.text() == value else None)
                note = 'В клиенте нажмите + → импорт из буфера обмена, затем подключитесь. Буфер очищается через минуту, если вы его не заменили.'
            self.service.open_client(p); self.status.setText(note)
        except (ValueError, OSError) as exc: self.status.setText(str(exc))

    def disconnect_selected(self):
        p = self.profiles.currentData()
        if p: self.run(lambda: self.service.disconnect(p))

    def choose_client(self):
        p = self.profiles.currentData()
        if not p or p['kind'] != 'external': return
        filename, _ = W.QFileDialog.getOpenFileName(self, 'Выберите установленный ' + p['client'], '', 'Программа (*.exe)')
        if filename:
            config = self.store.config.copy(); clients = dict(config.get('vpn_clients', {})); clients[p['client']] = filename
            config['vpn_clients'] = clients; self.store.save_config(config)

    def refresh_status(self):
        p = self.profiles.currentData()
        if p and p['kind'] == 'windows': self.run(self.service.statuses)
        else: self.selection()

    def poll(self):
        p = self.profiles.currentData()
        if self.isVisible() and not self.busy and p and p['kind'] == 'windows': self.refresh_status()

    def remove(self):
        p = self.profiles.currentData()
        if p and W.QMessageBox.question(self, 'Удалить профиль', 'Удалить выбранный профиль? Активный Windows VPN сначала отключите.') == W.QMessageBox.StandardButton.Yes:
            self.run(lambda: self.service.remove(p))
