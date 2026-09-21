"""Visual routine editor and selective learning from currently open programs."""
from .qt import QtWidgets as W, QtCore as C, Signal
from .design import glyph
from .workspaces import Workspaces


class WorkspacesPanel(W.QWidget):
    runRequested = Signal(str)

    def __init__(self, engine):
        super().__init__(); self.service = engine.workspaces; self.ident = None
        layout = W.QVBoxLayout(self)
        row = W.QHBoxLayout(); layout.addLayout(row)
        self.saved = W.QComboBox(); row.addWidget(self.saved, 1)
        self.saved.activated.connect(self.load)
        for text, callback in [('Новый', self.new), ('Сохранить', self.save), ('Удалить', self.remove), ('Запустить', self.run)]:
            b = W.QPushButton(text); b.clicked.connect(callback); row.addWidget(b)
        form = W.QFormLayout(); layout.addLayout(form)
        self.name = W.QLineEdit(); form.addRow('Название', self.name)
        self.triggers = W.QLineEdit(); self.triggers.setPlaceholderText('я начинаю работать; начинаем работу')
        form.addRow('Фразы запуска', self.triggers)
        self.steps = W.QTreeWidget(); self.steps.setHeaderLabels(['Действие', 'Значение']); self.steps.setRootIsDecorated(False)
        self.steps.setColumnWidth(0, 180); self.steps.itemDoubleClicked.connect(lambda *_: self.edit_step())
        layout.addWidget(self.steps, 1)
        row = W.QHBoxLayout(); layout.addLayout(row)
        for text, callback in [('Добавить шаг', self.add_step), ('Изменить', self.edit_step), ('Убрать', self.delete_step), ('↑', lambda: self.move(-1)), ('↓', lambda: self.move(1))]:
            b = W.QPushButton(text); b.clicked.connect(callback); row.addWidget(b)
        capture = W.QPushButton('Запомнить открытые программы'); capture.setIcon(glyph('vision'))
        capture.clicked.connect(self.capture); layout.addWidget(capture)
        note = W.QLabel('Откройте рабочие программы → выберите, что запомнить → добавьте сайты, музыку, яркость и громкость → сохраните. Сайты чужих вкладок не копируются: добавьте нужные ссылки отдельно. Двойной щелчок меняет шаг; Стоп прерывает запуск.')
        note.setWordWrap(True); layout.addWidget(note)
        self.status = W.QLabel(''); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.reload(); self.new()

    def reload(self):
        self.saved.clear(); self.saved.addItem('Выберите сохранённый сценарий', None)
        for p in self.service.profiles(): self.saved.addItem(p['name'], p)

    def new(self):
        self.ident = None; self.name.setText('Работа'); self.triggers.setText('я начинаю работать; начинаем работу')
        self.steps.clear(); self.status.setText('Добавьте нужные шаги и сохраните сценарий.')

    def load(self, index):
        p = self.saved.itemData(index)
        if not p: return
        self.ident = p['id']; self.name.setText(p['name']); self.triggers.setText('; '.join(p['triggers'])); self.steps.clear()
        for step in p['steps']: self.append(step)
        self.status.setText('Сценарий загружен. Изменения применяются после сохранения.')

    def append(self, step):
        item = W.QTreeWidgetItem([Workspaces.ACTIONS[step['action']], step['value']])
        item.setData(0, C.Qt.ItemDataRole.UserRole, step); self.steps.addTopLevelItem(item)

    def values(self):
        return [self.steps.topLevelItem(i).data(0, C.Qt.ItemDataRole.UserRole) for i in range(self.steps.topLevelItemCount())]

    def step_dialog(self, initial=None):
        dialog = W.QDialog(self); dialog.setWindowTitle('Шаг сценария'); dialog.resize(560, 210)
        form = W.QFormLayout(dialog); action = W.QComboBox()
        for key, text in Workspaces.ACTIONS.items(): action.addItem(text, key)
        value = W.QLineEdit(); form.addRow('Действие', action); form.addRow('Значение', value)
        hint = W.QLabel(); hint.setWordWrap(True); form.addRow(hint)
        def changed():
            hint.setText({'app': 'Название, например Telegram, или полный путь к EXE.', 'url': 'Полная ссылка https://…', 'music': 'Ссылка на плейлист. Сайт может потребовать нажатия Play.', 'folder': 'Полный путь к рабочей папке.', 'brightness': 'Число от 0 до 100.', 'volume': 'Число от 0 до 100.', 'power': 'balanced — баланс; performance — производительность; saver — экономия.', 'wait': 'Пауза от 0 до 30 секунд.'}[action.currentData()])
        action.currentIndexChanged.connect(changed); changed()
        if initial: action.setCurrentIndex(action.findData(initial['action'])); value.setText(initial['value'])
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok | W.QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons); buttons.rejected.connect(dialog.reject)
        result = []
        def accept():
            try: result.append(self.service.validate_step({'action': action.currentData(), 'value': value.text().strip()})); dialog.accept()
            except ValueError as exc: hint.setText(str(exc))
        buttons.accepted.connect(accept)
        dialog.exec(); return result[0] if result else None

    def add_step(self):
        step = self.step_dialog()
        if step: self.append(step)

    def edit_step(self):
        item = self.steps.currentItem()
        if not item: return
        step = self.step_dialog(item.data(0, C.Qt.ItemDataRole.UserRole))
        if step:
            item.setText(0, Workspaces.ACTIONS[step['action']]); item.setText(1, step['value']); item.setData(0, C.Qt.ItemDataRole.UserRole, step)

    def delete_step(self):
        index = self.steps.indexOfTopLevelItem(self.steps.currentItem())
        if index >= 0: self.steps.takeTopLevelItem(index)

    def move(self, offset):
        index = self.steps.indexOfTopLevelItem(self.steps.currentItem()); target = index + offset
        if index >= 0 and 0 <= target < self.steps.topLevelItemCount():
            item = self.steps.takeTopLevelItem(index); self.steps.insertTopLevelItem(target, item); self.steps.setCurrentItem(item)

    def save(self):
        try:
            p = self.service.save(self.name.text(), [t.strip() for t in self.triggers.text().split(';') if t.strip()], self.values(), self.ident)
            self.ident = p['id']; self.reload(); self.status.setText('Сохранено. Скажите: «'+p['triggers'][0]+'».'); return p
        except (ValueError, OSError) as exc: self.status.setText(str(exc)); return None

    def run(self):
        p = self.save()
        if p: self.runRequested.emit('запусти сценарий '+p['name'])

    def remove(self):
        if self.ident and W.QMessageBox.question(self, 'Удалить сценарий', 'Удалить текущий сохранённый сценарий?') == W.QMessageBox.StandardButton.Yes:
            self.service.remove(self.ident); self.reload(); self.new()

    def capture(self):
        try: apps = self.service.visible_apps()
        except Exception: self.status.setText('Не удалось прочитать список открытых программ. Добавьте их по названию.'); return
        dialog = W.QDialog(self); dialog.setWindowTitle('Что запомнить для работы'); dialog.resize(650, 450)
        layout = W.QVBoxLayout(dialog); listing = W.QListWidget(); layout.addWidget(listing)
        for app in apps:
            item = W.QListWidgetItem(app['title']); item.setToolTip(app['path'])
            item.setData(C.Qt.ItemDataRole.UserRole, app['path']); item.setCheckState(C.Qt.CheckState.Unchecked); listing.addItem(item)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok | W.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() != W.QDialog.DialogCode.Accepted: return
        existing = {step['value'] for step in self.values() if step['action'] == 'app'}
        for index in range(listing.count()):
            item = listing.item(index); path = item.data(C.Qt.ItemDataRole.UserRole)
            if item.checkState() == C.Qt.CheckState.Checked and path not in existing:
                self.append({'action': 'app', 'value': path}); existing.add(path)
        self.status.setText('Выбранные программы добавлены. Добавьте ссылки и параметры, затем сохраните.')
