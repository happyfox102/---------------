from __future__ import annotations

from pathlib import Path

from .qt import QtCore as C, QtWidgets as W, Signal
from .design import glyph, button as style_button, LoadingBar
from .security import SecurityService


class DropList(W.QListWidget):
    changed = Signal()
    def __init__(self, placeholder="Перетащите сюда ярлык или файл"):
        super().__init__(); self.setAcceptDrops(True); self.setToolTip(placeholder); self.setMinimumHeight(78)
        self.setStyleSheet("QListWidget { border:1px dashed #3c5368; border-radius:10px; padding:6px; }")
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.exists() and not self.findItems(str(path), C.Qt.MatchFlag.MatchExactly): self.addItem(str(path))
        self.changed.emit(); event.acceptProposedAction()
    def values(self): return [self.item(i).text() for i in range(self.count())]
    def set_values(self, values):
        self.clear(); [self.addItem(str(v)) for v in values if Path(v).exists()]


class SecurityPanel(W.QWidget):
    message = Signal(str)
    activeChanged = Signal(bool)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.service = store, SecurityService(store)
        self.monitoring = False; self.parental = False
        self.last_snapshot = 0
        self.timer = C.QTimer(self); self.timer.setInterval(5000); self.timer.timeout.connect(self.tick)
        self.timer.start(); self.service.poll_processes()
        layout = W.QVBoxLayout(self)
        title = W.QLabel("Защитник"); title.setObjectName("sectionTitle"); layout.addWidget(title)
        self.state = W.QLabel("Защита не активна"); self.state.setObjectName("detailCard"); layout.addWidget(self.state)
        self.tabs = W.QTabWidget(); layout.addWidget(self.tabs, 1)
        self._defender_page(); self._watch_page(); self._guard_page(); self._parent_page()
        self.refresh_defender()

    def _defender_page(self):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        self.defender = W.QLabel("Проверяю Microsoft Defender…"); self.defender.setWordWrap(True); layout.addWidget(self.defender)
        row=W.QHBoxLayout(); refresh=W.QPushButton(); style_button(refresh,'restore',icon_only=True); refresh.setToolTip("Обновить статус"); refresh.clicked.connect(self.refresh_defender); row.addWidget(refresh)
        scan=W.QPushButton(); style_button(scan,'search',icon_only=True); scan.setToolTip("Быстрая проверка Defender"); scan.clicked.connect(self.start_scan); row.addWidget(scan)
        open_security=W.QPushButton(); style_button(open_security,'shield',icon_only=True); open_security.setToolTip("Открыть Безопасность Windows"); open_security.clicked.connect(lambda: __import__('os').system('start windowsdefender:')); row.addWidget(open_security); row.addStretch(); layout.addLayout(row)
        hint=W.QLabel("Пятница использует встроенный Microsoft Defender: показывает его состояние и может запустить быструю проверку."); hint.setWordWrap(True); layout.addWidget(hint); layout.addStretch()
        self.tabs.addTab(page, glyph('shield'), 'Антивирус')

    def _watch_page(self):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        self.watch_button=W.QPushButton(); style_button(self.watch_button,'vision',icon_only=True); self.watch_button.setToolTip('Включить наблюдение'); self.watch_button.clicked.connect(self.toggle_watch)
        self.report_button=W.QPushButton(); style_button(self.report_button,'file',icon_only=True); self.report_button.setToolTip('Создать локальный отчёт'); self.report_button.clicked.connect(self.create_report)
        self.screen_check=W.QCheckBox('Снимки экрана'); self.screen_check.setChecked(self.store.config.get('security_snapshots', True))
        self.interval=W.QSpinBox(); self.interval.setRange(30, 600); self.interval.setSingleStep(30); self.interval.setValue(self.store.config.get('security_snapshot_seconds', 60)); self.interval.setSuffix(' сек')
        row=W.QHBoxLayout(); row.addWidget(self.watch_button); row.addWidget(self.report_button); row.addStretch(); layout.addLayout(row)
        form=W.QFormLayout(); form.addRow('Экран', self.screen_check); form.addRow('Интервал', self.interval); layout.addLayout(form)
        self.watch_info=W.QLabel('Выключено. После включения Пятница локально записывает запуск и закрытие приложений.'); self.watch_info.setWordWrap(True); layout.addWidget(self.watch_info)
        note=W.QLabel('Наблюдение видно в этом разделе. Снимки и отчёты хранятся только в data/security; их можно отключить в любой момент.'); note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.tabs.addTab(page, glyph('vision'), 'Присмотр')

    def _guard_page(self):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        row=W.QHBoxLayout(); arm=W.QPushButton(); style_button(arm,'shield',icon_only=True); arm.setToolTip('Охранять ПК: заблокировать Windows'); arm.clicked.connect(self.arm); row.addWidget(arm)
        remove=W.QPushButton(); style_button(remove,'trash',icon_only=True); remove.setToolTip('Удалить выбранное правило'); remove.clicked.connect(lambda: self.remove_selected(self.protected)); row.addWidget(remove); row.addStretch(); layout.addLayout(row)
        layout.addWidget(W.QLabel('Защищённые файлы и ярлыки'))
        self.protected=DropList(); self.protected.set_values(self.store.config.get('security_protected_files', [])); self.protected.changed.connect(self.save_rules); layout.addWidget(self.protected)
        note=W.QLabel('Охрана блокирует сессию Windows. Для доступа нужен пароль Windows, поэтому документы и программы недоступны постороннему. Перетащите сюда важные файлы и ярлыки, чтобы видеть их в правилах и отчётах.'); note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.tabs.addTab(page, glyph('shield'), 'Охрана')

    def _parent_page(self):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        row=W.QHBoxLayout(); self.parent_button=W.QPushButton(); style_button(self.parent_button,'profile',icon_only=True); self.parent_button.setToolTip('Включить родительский контроль'); self.parent_button.clicked.connect(self.toggle_parental); row.addWidget(self.parent_button)
        remove=W.QPushButton(); style_button(remove,'trash',icon_only=True); remove.setToolTip('Удалить выбранное приложение'); remove.clicked.connect(lambda: self.remove_selected(self.allowed)); row.addWidget(remove); row.addStretch(); layout.addLayout(row)
        layout.addWidget(W.QLabel('Разрешённые приложения'))
        self.allowed=DropList(); self.allowed.set_values(self.store.config.get('security_allowed_apps', [])); self.allowed.changed.connect(self.save_rules); layout.addWidget(self.allowed)
        form=W.QFormLayout(); self.parent_start=W.QLineEdit(self.store.config.get('security_parent_start','')); self.parent_start.setPlaceholderText('например 09:00'); self.parent_end=W.QLineEdit(self.store.config.get('security_parent_end','')); self.parent_end.setPlaceholderText('например 21:00'); form.addRow('Разрешено с', self.parent_start); form.addRow('До', self.parent_end); layout.addLayout(form)
        note=W.QLabel('Режим отмечает запуск непривычных приложений и сохраняет это в локальный отчёт. Для реального ограничения доступа используйте отдельную учётную запись Windows и «Охрану» с блокировкой сессии.'); note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.tabs.addTab(page, glyph('profile'), 'Родительский контроль')

    def remove_selected(self, widget):
        for item in widget.selectedItems(): widget.takeItem(widget.row(item))
        self.save_rules()

    def save_rules(self):
        config=self.store.config.copy(); config.update(security_protected_files=self.protected.values(), security_allowed_apps=self.allowed.values(), security_snapshots=self.screen_check.isChecked(), security_snapshot_seconds=self.interval.value(), security_parent_start=self.parent_start.text().strip(), security_parent_end=self.parent_end.text().strip())
        self.store.save_config(config)

    def refresh_defender(self): self.defender.setText(self.service.defender_status())
    def start_scan(self):
        if W.QMessageBox.question(self,'Microsoft Defender','Запустить быструю проверку Microsoft Defender?') == W.QMessageBox.StandardButton.Yes:
            self.message.emit(self.service.quick_scan()); self.refresh_defender()

    def toggle_watch(self):
        self.monitoring=not self.monitoring; self.save_rules(); self.watch_button.setToolTip('Остановить наблюдение' if self.monitoring else 'Включить наблюдение')
        self.watch_info.setText('Наблюдение включено · локальный журнал активен.' if self.monitoring else 'Выключено. Журнал остаётся на этом ПК.')
        self.state.setText('Присмотр активен' if self.monitoring else 'Защита не активна'); self.activeChanged.emit(self.monitoring)
        self.service.event('watch_started' if self.monitoring else 'watch_stopped')

    def tick(self):
        if not (self.monitoring or self.parental): return
        allowed={Path(x).name.casefold() for x in self.allowed.values()}
        started=self.service.poll_processes(allowed, self.parental)
        if started and self.parental:
            restricted=[name for _,name in started if allowed and name.casefold() not in allowed]
            if restricted: self.watch_info.setText('Отмечено: ' + ', '.join(restricted[:3]))
        now=C.QDateTime.currentSecsSinceEpoch()
        if self.monitoring and self.screen_check.isChecked() and now-self.last_snapshot >= self.interval.value():
            self.service.screenshot(); self.last_snapshot=now

    def create_report(self):
        report=self.service.build_report(); self.message.emit(f'Отчёт Защитника сохранён: {report}')

    def arm(self):
        self.save_rules()
        if W.QMessageBox.question(self,'Охрана','Заблокировать сессию Windows сейчас? Для возврата потребуется пароль Windows.') == W.QMessageBox.StandardButton.Yes:
            if self.service.lock_workstation(): self.message.emit('Охрана включена: Windows заблокирована.')
            else: self.message.emit('Не удалось заблокировать Windows.')

    def toggle_parental(self):
        self.parental=not self.parental; self.save_rules(); self.parent_button.setToolTip('Выключить родительский контроль' if self.parental else 'Включить родительский контроль')
        self.state.setText('Родительский контроль активен' if self.parental else 'Защита не активна')
        self.service.event('parental_started' if self.parental else 'parental_stopped')

    def command(self, text):
        cmd=text.casefold()
        if 'защитник' in cmd or 'антивирус' in cmd:
            self.tabs.setCurrentIndex(0); self.refresh_defender(); return 'Открыла Защитник: статус Microsoft Defender обновлён.'
        if 'охраняй' in cmd or 'охрана пк' in cmd:
            self.tabs.setCurrentIndex(2); self.arm(); return 'Охрана открыта.'
        if 'начни присмотр' in cmd or 'следи за пк' in cmd:
            self.tabs.setCurrentIndex(1)
            if not self.monitoring: self.toggle_watch()
            return 'Присмотр включён. Журнал и снимки хранятся локально.'
        if 'останови присмотр' in cmd:
            if self.monitoring: self.toggle_watch()
            return 'Присмотр остановлен.'
        if 'отчёт защитника' in cmd:
            self.create_report(); return 'Создаю локальный отчёт Защитника.'
        return None
