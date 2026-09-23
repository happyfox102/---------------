from __future__ import annotations

from pathlib import Path
import threading
import json

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
    jobDone = Signal(str, str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.service = store, SecurityService(store)
        self.monitoring = False; self.parental = False
        self.last_snapshot = 0
        self.child_browser = None
        self.pin_failures = 0
        self.pin_retry_after = 0
        self.job_busy = False
        self.poll_busy = False
        self.jobDone.connect(self.job_done)
        self.timer = C.QTimer(self); self.timer.setInterval(10000); self.timer.timeout.connect(self.tick)
        layout = W.QVBoxLayout(self)
        title = W.QLabel("Защитник"); title.setObjectName("sectionTitle"); layout.addWidget(title)
        self.state = W.QLabel("Защита не активна"); self.state.setObjectName("detailCard"); layout.addWidget(self.state)
        self.tabs = W.QTabWidget(); layout.addWidget(self.tabs, 1)
        self._defender_page(); self._watch_page(); self._guard_page(); self._parent_page()
        self.tabs.hide()
        self.reports = W.QTreeWidget()
        self.reports.setHeaderLabels(['Время', 'Событие', 'Результат', 'Подробности'])
        self.reports.setRootIsDecorated(False)
        self.reports.setAlternatingRowColors(True)
        self.reports.header().setSectionResizeMode(3, W.QHeaderView.ResizeMode.Stretch)
        self.reports.itemDoubleClicked.connect(self.open_report_item)
        layout.addWidget(self.reports, 1)
        self.report_stamp = None

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_report()

    def refresh_report(self):
        stamp = self.service.events.stat().st_mtime_ns if self.service.events.exists() else 0
        if stamp == self.report_stamp:
            return
        self.report_stamp = stamp
        self.reports.clear()
        labels = {'app_started':'Запуск приложения', 'app_closed':'Закрытие приложения',
                  'rules_saved':'Правила сохранены', 'pin_denied':'Доступ к настройкам',
                  'defender_scan_requested':'Проверка антивирусом',
                  'defender_scan_finished':'Проверка антивирусом завершена',
                  'defender_scan_failed':'Ошибка антивируса',
                  'snapshot':'Снимок экрана', 'guard_lock':'Блокировка Windows',
                  'guard_cancelled':'Охрана отменена', 'browser_block':'Сайт заблокирован',
                  'browser_visit':'Открытие сайта', 'ai_review':'Оценка ИИ',
                  'watch_started':'Присмотр включён', 'watch_stopped':'Присмотр выключен',
                  'parental_started':'Контроль включён', 'parental_stopped':'Контроль выключен'}
        outcomes = {'observed':'Записано', 'blocked':'Запрещено', 'requested':'Запрошено',
                    'failed':'Ошибка', 'cancelled':'Отменено', 'completed':'Выполнено'}
        for row in reversed(self.service.recent()):
            detail = row.get('reason') or row.get('app') or row.get('file') or ''
            if row.get('restricted'):
                detail += ' · вне списка; запуск наблюдался, блокировка не выполнялась'
            item = W.QTreeWidgetItem([row.get('time','').replace('T',' '),
                labels.get(row.get('kind'),row.get('kind','')), outcomes.get(row.get('outcome','observed'),row.get('outcome','')), detail])
            if row.get('file'):
                item.setData(0, C.Qt.ItemDataRole.UserRole, str(self.service.shots / row['file']))
                item.setToolTip(3, 'Двойной щелчок — открыть снимок')
            self.reports.addTopLevelItem(item)

    def open_report_item(self, item, _column):
        path = item.data(0, C.Qt.ItemDataRole.UserRole)
        if path and Path(path).is_file():
            try:
                import os
                os.startfile(path)
            except OSError:
                pass

    def attach_settings(self, dialog, layout):
        layout.addWidget(self.tabs)
        self.tabs.show()
        def detach(_):
            self.tabs.setParent(self)
            self.tabs.hide()
        dialog.finished.connect(detach)

    def run_job(self, kind, function):
        if self.job_busy:
            return
        self.job_busy = True
        self.defender.setText('Проверяю…')
        def work():
            try:
                result = function()
            except Exception as exc:
                result = 'Ошибка: ' + str(exc)
            self.jobDone.emit(kind, str(result))
        threading.Thread(target=work, daemon=True, name='security-request').start()

    def job_done(self, kind, result):
        self.job_busy = False
        self.defender.setText(result)
        if kind != 'status':
            self.message.emit(result)
        self.refresh_report()

    def _defender_page(self):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        self.defender = W.QLabel('Microsoft Defender · нажмите обновление для проверки'); self.defender.setWordWrap(True); layout.addWidget(self.defender)
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
        note=W.QLabel('Охрана блокирует сессию Windows: для возврата нужен пароль Windows. Список файлов — памятка; отдельные права доступа он не меняет. Запрос, ошибка и отмена записываются в журнал. Попытки запуска в заблокированной сессии Пятнице недоступны.'); note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.tabs.addTab(page, glyph('shield'), 'Охрана')

    def _parent_page(self):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        row=W.QHBoxLayout(); self.parent_button=W.QPushButton(); style_button(self.parent_button,'profile',icon_only=True); self.parent_button.setToolTip('Включить родительский контроль'); self.parent_button.clicked.connect(self.toggle_parental); row.addWidget(self.parent_button)
        remove=W.QPushButton(); style_button(remove,'trash',icon_only=True); remove.setToolTip('Удалить выбранное приложение'); remove.clicked.connect(lambda: self.remove_selected(self.allowed)); row.addWidget(remove); row.addStretch(); layout.addLayout(row)
        layout.addWidget(W.QLabel('Приложения для сравнения с журналом (запуск не блокируется)'))
        self.allowed=DropList(); self.allowed.set_values(self.store.config.get('security_allowed_apps', [])); self.allowed.changed.connect(self.save_rules); layout.addWidget(self.allowed)
        form=W.QFormLayout(); self.parent_start=W.QLineEdit(self.store.config.get('security_parent_start','')); self.parent_start.setPlaceholderText('например 09:00'); self.parent_end=W.QLineEdit(self.store.config.get('security_parent_end','')); self.parent_end.setPlaceholderText('например 21:00'); form.addRow('Разрешено с', self.parent_start); form.addRow('До', self.parent_end); layout.addLayout(form)
        self.site_allow = W.QPlainTextEdit('\n'.join(self.store.config.get('security_allowed_sites', [])))
        self.site_allow.setPlaceholderText('Разрешённые домены, по одному в строке. Например: wikipedia.org')
        self.site_allow.setMaximumHeight(75); layout.addWidget(self.site_allow)
        self.site_block = W.QPlainTextEdit('\n'.join(self.store.config.get('security_blocked_sites', [])))
        self.site_block.setPlaceholderText('Запрещённые домены (имеют приоритет)')
        self.site_block.setMaximumHeight(65); layout.addWidget(self.site_block)
        self.ai_review = W.QCheckBox('Оценка запросов ИИ')
        self.ai_review.setToolTip('Только в детском браузере: запрос отправляется выбранному ИИ. Не чаще одного раза в минуту. Оценка может ошибаться; неизвестные сайты остаются закрыты.')
        self.ai_review.setChecked(self.store.config.get('security_ai_review', False)); layout.addWidget(self.ai_review)
        row = W.QHBoxLayout()
        save = W.QPushButton('Сохранить правила'); style_button(save,'success',icon_only=True); save.clicked.connect(self.apply_rules); row.addWidget(save)
        browser = W.QPushButton('Детский браузер'); style_button(browser,'globe',icon_only=True); browser.clicked.connect(self.open_child_browser); row.addWidget(browser)
        pin = W.QPushButton('Установить PIN родителя'); style_button(pin,'shield',icon_only=True); pin.clicked.connect(self.change_pin); row.addWidget(pin)
        row.addStretch(); layout.addLayout(row)
        note=W.QLabel('Браузер Пятницы: только разрешённые HTTPS-домены, расписание, без загрузок и новых окон. Сайты вне списка, в том числе 18+, закрыты. В других браузерах правила не действуют. ИИ даёт оценку риска запроса, а не проверку репутации сайта.'); note.setWordWrap(True); layout.addWidget(note)
        self.tabs.addTab(page, glyph('profile'), 'Родительский контроль')

    def remove_selected(self, widget):
        for item in widget.selectedItems(): widget.takeItem(widget.row(item))
        self.save_rules()

    def save_rules(self):
        config=self.store.config.copy(); config.update(security_protected_files=self.protected.values(), security_allowed_apps=self.allowed.values(), security_snapshots=self.screen_check.isChecked(), security_snapshot_seconds=self.interval.value(), security_parent_start=self.parent_start.text().strip(), security_parent_end=self.parent_end.text().strip())
        self.store.save_config(config)

    def apply_rules(self):
        from .child_policy import domain
        from datetime import datetime
        try:
            start, end = self.parent_start.text().strip(), self.parent_end.text().strip()
            if start or end:
                datetime.strptime(start, '%H:%M'); datetime.strptime(end, '%H:%M')
                if start == end:
                    raise ValueError('Начало и конец расписания должны различаться.')
            allow = [domain(x) for x in self.site_allow.toPlainText().splitlines() if x.strip()]
            deny = [domain(x) for x in self.site_block.toPlainText().splitlines() if x.strip()]
            if any(not x or '.' not in x for x in allow + deny):
                raise ValueError('Укажите домены, например wikipedia.org.')
            self.save_rules()
            config = self.store.config.copy()
            config.update(security_allowed_sites=allow,security_blocked_sites=deny,security_ai_review=self.ai_review.isChecked())
            self.store.save_config(config)
            if self.child_browser:
                self.child_browser.config.clear(); self.child_browser.config.update(config)
                self.child_browser.check_time()
                self.child_browser.view.setUrl(C.QUrl('about:blank'))
            self.service.event('rules_saved', outcome='completed',reason='Обновлены правила детского браузера')
            self.refresh_report()
            return True
        except ValueError as exc:
            W.QMessageBox.warning(self,'Проверьте правила',str(exc))
            return False

    def authorize(self):
        from .child_policy import check_pin
        import time
        if time.monotonic() < self.pin_retry_after:
            return False
        encoded = self.store.config.get('security_parent_pin','')
        if not encoded:
            return False
        pin, ok = W.QInputDialog.getText(self,'Родительский доступ','PIN:',W.QLineEdit.EchoMode.Password)
        if ok and check_pin(pin,encoded):
            self.pin_failures = 0
            return True
        if ok:
            self.pin_failures += 1
            if self.pin_failures >= 5:
                self.pin_retry_after = time.monotonic() + 60
            self.service.event('pin_denied',outcome='blocked',reason='Неверный PIN родителя')
        return False

    def change_pin(self):
        from .child_policy import set_pin
        if self.store.config.get('security_parent_pin') and not self.authorize():
            return
        pin, ok = W.QInputDialog.getText(self,'PIN родителя','Новый PIN (6–12 цифр):',W.QLineEdit.EchoMode.Password)
        if not ok: return
        try:
            encoded = set_pin(pin)
            config = self.store.config.copy(); config['security_parent_pin'] = encoded; self.store.save_config(config)
        except ValueError as exc:
            W.QMessageBox.warning(self,'PIN',str(exc))

    def open_child_browser(self):
        if not self.parental:
            W.QMessageBox.information(self,'Родительский контроль','Сначала сохраните правила, установите PIN и включите контроль.')
            return
        try:
            if self.child_browser is None:
                from .child_browser import ChildBrowser
                self.child_browser = ChildBrowser(self.service, self.store.config)
                self.child_browser.notice.connect(self.message.emit)
            self.child_browser.clock.start()
            self.child_browser.show(); self.child_browser.raise_()
        except ImportError:
            W.QMessageBox.warning(self,'Браузер','Компонент Qt WebEngine отсутствует в этой сборке.')

    def refresh_defender(self): self.run_job('status', self.service.defender_status)
    def start_scan(self):
        if W.QMessageBox.question(self,'Microsoft Defender','Запустить быструю проверку Microsoft Defender?') == W.QMessageBox.StandardButton.Yes:
            self.run_job('scan', self.service.quick_scan)

    def toggle_watch(self):
        self.monitoring=not self.monitoring; self.save_rules(); self.watch_button.setToolTip('Остановить наблюдение' if self.monitoring else 'Включить наблюдение')
        self.watch_info.setText('Наблюдение включено · локальный журнал активен.' if self.monitoring else 'Выключено. Журнал остаётся на этом ПК.')
        self.state.setText('Присмотр активен' if self.monitoring else 'Защита не активна'); self.activeChanged.emit(self.monitoring)
        self.service.event('watch_started' if self.monitoring else 'watch_stopped')
        self.update_timer()

    def update_timer(self):
        active = self.monitoring or self.parental
        self.activeChanged.emit(active)
        if active and not self.timer.isActive():
            self.service.baseline = False
            self.timer.start()
        elif not active:
            self.timer.stop()
        self.state.setText(' · '.join(x for x, on in [('Присмотр',self.monitoring),('Родительский контроль',self.parental)] if on) or 'Нет активных сеансов')
        self.refresh_report()

    def tick(self):
        if not (self.monitoring or self.parental): return
        allowed={Path(x).name.casefold() for x in self.allowed.values()}
        if not self.poll_busy:
            self.poll_busy = True
            def poll():
                try:
                    self.service.poll_processes(allowed, self.parental)
                finally:
                    self.poll_busy = False
            threading.Thread(target=poll, daemon=True, name='security-poll').start()
        now=C.QDateTime.currentSecsSinceEpoch()
        if self.monitoring and self.screen_check.isChecked() and now-self.last_snapshot >= self.interval.value():
            self.service.screenshot(); self.last_snapshot=now
        if self.isVisible():
            self.refresh_report()

    def create_report(self):
        report=self.service.build_report(); self.message.emit(f'Отчёт Защитника сохранён: {report}')

    def arm(self):
        self.save_rules()
        if W.QMessageBox.question(self,'Охрана','Заблокировать сессию Windows сейчас? Для возврата потребуется пароль Windows.') == W.QMessageBox.StandardButton.Yes:
            if self.service.lock_workstation(): self.message.emit('Охрана включена: Windows заблокирована.')
            else: self.message.emit('Не удалось заблокировать Windows.')
        else:
            self.service.event('guard_cancelled', outcome='cancelled', reason='Пользователь отменил блокировку')
        self.refresh_report()

    def toggle_parental(self):
        if self.parental and not self.authorize():
            return
        if not self.parental:
            if not self.store.config.get('security_parent_pin'):
                self.change_pin()
                if not self.store.config.get('security_parent_pin'): return
            if not self.apply_rules(): return
        self.parental=not self.parental; self.save_rules(); self.parent_button.setToolTip('Выключить родительский контроль' if self.parental else 'Включить родительский контроль')
        self.state.setText('Родительский контроль активен' if self.parental else 'Защита не активна')
        self.activeChanged.emit(self.parental or self.monitoring)
        self.service.event('parental_started' if self.parental else 'parental_stopped')
        self.update_timer()
        if not self.parental and self.child_browser:
            self.child_browser.close()

    def command(self, text):
        cmd=text.casefold()
        if 'отчёт защитника' in cmd or 'отчет защитника' in cmd:
            self.create_report(); return 'Локальный отчёт Защитника сохранён.'
        if 'детский браузер' in cmd:
            self.open_child_browser(); return 'Детский браузер доступен после включения родительского контроля в настройках.'
        if 'защитник' in cmd or 'антивирус' in cmd:
            self.refresh_report(); return 'Открыла журнал Защитника. Управление — в настройках.'
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
