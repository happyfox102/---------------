"""PC dashboard with live charts, storage breakdown and reversible profiles."""
import os
import threading
import psutil

from .qt import QtCore as C, QtGui as G, QtWidgets as W, Signal
from .pc_services import Metrics, Optimizer, scan_disk
from .design import current_palette, glyph, button as style_button, LoadingBar

COLORS = ["#73dfc1", "#7ea8ff", "#d2a0ff", "#ffbc75", "#f180a3", "#b6d875", "#79d6ea", "#8794ad", "#5b6982"]


def size_text(value):
    return f"{value / 1024**3:.1f} ГБ" if value >= 1024**3 else f"{value / 1024**2:.0f} МБ"


class Gauge(W.QWidget):
    def __init__(self, title, color):
        super().__init__()
        self.title, self.color = title, color
        self.values = []
        self.value = None
        self.setMinimumSize(160, 180)

    def sample(self, value):
        self.value = value
        self.values = (self.values + [value or 0])[-60:]
        self.update()

    def paintEvent(self, event):
        p = G.QPainter(self)
        p.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        theme = current_palette()
        p.fillRect(self.rect(), G.QColor(theme['surface']))
        p.setPen(G.QColor(theme['fg']))
        p.drawText(C.QRect(12, 6, self.width()-24, 25), C.Qt.AlignmentFlag.AlignLeft, self.title)
        box = C.QRectF((self.width()-94)/2, 39, 94, 94)
        p.setPen(G.QPen(G.QColor(theme['border']), 9))
        p.drawArc(box, 0, 5760)
        p.setPen(G.QPen(G.QColor(self.color), 9))
        p.drawArc(box, 90*16, -int((self.value or 0)*57.6))
        font = p.font(); font.setPointSize(19); font.setBold(True); p.setFont(font)
        p.drawText(box, C.Qt.AlignmentFlag.AlignCenter, f"{self.value:.0f}%" if self.value is not None else "—")
        if len(self.values) > 1:
            path = G.QPainterPath()
            for i, value in enumerate(self.values):
                x, y = 12 + i*(self.width()-24)/59, self.height()-10-value*.25
                path.moveTo(x, y) if not i else path.lineTo(x, y)
            p.setPen(G.QPen(G.QColor(self.color), 2)); p.drawPath(path)
        p.end()


class DiskBar(W.QWidget):
    def __init__(self):
        super().__init__(); self.parts = []; self.setMinimumHeight(35)

    def paintEvent(self, event):
        p = G.QPainter(self); x = 0
        total = sum(v for _, v in self.parts) or 1
        for i, (_, value) in enumerate(self.parts):
            width = self.width()*value/total
            p.fillRect(C.QRectF(x, 4, width, 25), G.QColor(COLORS[i % len(COLORS)])); x += width
        p.end()


class PCPanel(W.QWidget):
    message = Signal(str)
    scanResult = Signal(dict, int, int, bool)
    jobDone = Signal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.optimizer = Optimizer(store)
        self.metrics = Metrics()
        self.metrics.sample.connect(self.update_metrics)
        self.cancel = threading.Event()
        self.scan_thread = None
        self.busy = False
        self.scanResult.connect(self.update_disk)
        self.jobDone.connect(self.job_finished)
        outer = W.QVBoxLayout(self)
        title = W.QLabel("Мой ПК")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        self.loading = LoadingBar(); outer.addWidget(self.loading)
        self.loading.loading(True, "Получаю показатели ПК")
        self.tabs = W.QTabWidget(); outer.addWidget(self.tabs)
        self.pages = {}
        for key, label in (("overview", "Нагрузка"), ("hardware", "Характеристики"), ("disk", "Хранилище"), ("modes", "Режимы и задачи")):
            page = W.QWidget(); layout = W.QVBoxLayout(page)
            self.pages[key] = (page, layout); self.tabs.addTab(page, glyph({'overview':'chart','hardware':'pc','disk':'disk','modes':'bolt'}[key]), label)
        layout = self.pages["overview"][1]
        charts = W.QHBoxLayout(); self.gauges = {}
        for key, name, color in (("cpu", "Процессор", COLORS[0]), ("ram", "Память RAM", COLORS[1]), ("gpu", "Видеокарта GPU", COLORS[2])):
            gauge = Gauge(name, color); charts.addWidget(gauge); self.gauges[key] = gauge
        layout.addLayout(charts)
        self.memory = W.QLabel("Собираю показатели…"); self.memory.setWordWrap(True); layout.addWidget(self.memory)
        self.memory.setToolTip("История: последние 60 замеров. «—» означает, что драйвер не отдаёт показатель.")
        self.details = W.QLabel("Питание и активность диска появятся после первого замера.")
        self.details.setObjectName("detailCard")
        self.details.setWordWrap(True); layout.addWidget(self.details)
        self.health = W.QLabel(); self.health.setWordWrap(True); layout.addWidget(self.health)
        layout.addStretch()
        self.hardware = W.QTextBrowser(); self.pages["hardware"][1].addWidget(self.hardware)
        layout = self.pages["disk"][1]
        row = W.QHBoxLayout(); self.drives = W.QComboBox()
        for part in psutil.disk_partitions():
            if part.fstype:
                self.drives.addItem(f"{part.mountpoint} · {part.fstype}", part.mountpoint)
        self.drives.currentIndexChanged.connect(self.disk_usage)
        row.addWidget(self.drives)
        self.scan_button = W.QPushButton("Анализировать диск"); self.scan_button.clicked.connect(self.start_scan); row.addWidget(self.scan_button)
        stop = W.QPushButton("Отменить"); stop.clicked.connect(self.cancel.set); row.addWidget(stop); layout.addLayout(row)
        self.disk_status = W.QLabel(); self.disk_status.setWordWrap(True); layout.addWidget(self.disk_status)
        self.scan_progress = LoadingBar(); layout.addWidget(self.scan_progress)
        style_button(self.scan_button, 'search', 'Анализировать'); style_button(stop, 'close', icon_only=True)
        self.disk_bar = DiskBar(); layout.addWidget(self.disk_bar)
        self.categories = W.QTextBrowser(); layout.addWidget(self.categories)
        layout.addWidget(W.QLabel("Оценка по путям и типам файлов. Сжатие, доступ и системные данные влияют на итог.\nСодержимое файлов не читается. Анализ можно отменить."))
        self.disk_usage()
        layout = self.pages["modes"][1]
        row = W.QHBoxLayout()
        self.mode_buttons = []
        for label, mode in (("Игровой", "game"), ("Рабочий", "work"), ("Экономия", "save")):
            button = W.QPushButton(label); button.clicked.connect(lambda checked=False, m=mode: self.profile(m)); row.addWidget(button); self.mode_buttons.append(button)
            style_button(button, {'game':'game','work':'briefcase','save':'leaf'}[mode])
        layout.addLayout(row)
        info = W.QLabel("Игровой: производительность, яркость 100%, ниже приоритет фоновых приложений.\nРабочий: баланс, яркость 70%. Экономия: энергоэффективность, яркость 40%.\nОптимизация не закрывает приложения и не обещает освободить занятую ими память.")
        info.setToolTip(info.text()); info.setText("Профиль меняет питание, яркость и приоритет фоновых задач.")
        info.setWordWrap(True); layout.addWidget(info)
        self.processes = W.QTableWidget(0, 4)
        self.processes.setHorizontalHeaderLabels(["Выбор / приложение", "PID", "CPU %", "Память"])
        self.processes.horizontalHeader().setSectionResizeMode(0, W.QHeaderView.ResizeMode.Stretch)
        self.processes.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.processes)
        row = W.QHBoxLayout()
        optimize = W.QPushButton("⚡ Ускорить ПК"); optimize.clicked.connect(self.optimize); row.addWidget(optimize)
        close = W.QPushButton("Закрыть выбранные…"); close.clicked.connect(self.close_selected); row.addWidget(close)
        restore = W.QPushButton("Вернуть настройки"); restore.clicked.connect(lambda: self.run_job(self.optimizer.restore)); row.addWidget(restore)
        layout.addLayout(row)
        release = W.QPushButton("Освободить память локального ИИ")
        release.clicked.connect(lambda: self.run_job(self.optimizer.release_ai)); layout.addWidget(release)
        for control, name, label in ((optimize,'bolt','Ускорить'),(close,'close','Закрыть выбранные…'),(restore,'restore','Восстановить'),(release,'leaf','Выгрузить ИИ из памяти')):
            style_button(control, name, label)
        self.job_progress = LoadingBar(); layout.addWidget(self.job_progress)
        self.job_status = W.QLabel("Без выбора в таблице оптимизируются подходящие фоновые приложения. Активное окно исключается.")
        self.job_status.setWordWrap(True); layout.addWidget(self.job_status)

    def showEvent(self, event):
        super().showEvent(event)
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self.metrics.start()

    def hideEvent(self, event):
        self.metrics.visible.clear()
        super().hideEvent(event)

    def show_page(self, key):
        self.tabs.setCurrentWidget(self.pages[key][0])

    def update_metrics(self, data):
        self.loading.loading(False)
        for key, gauge in self.gauges.items():
            gauge.sample(data[key])
        self.memory.setText(f"Память: {size_text(data['used'])} из {size_text(data['total'])}. GPU: " + ("наиболее загруженный движок" if data["gpu"] is not None else "счётчик недоступен"))
        battery = data.get("battery")
        power = f"Батарея {battery[0]:.0f}% · {'от сети' if battery[1] else 'автономная работа'}" if battery else "Данные батареи недоступны"
        self.details.setText(f"{power}\nДиск: {size_text(max(0, data.get('disk_rate', 0)))}/с  •  Загрузка из сети: {size_text(max(0, data.get('download', 0)))}/с\nЧастота CPU: {(data.get('frequency') or 0)/1000:.2f} ГГц")
        self.health.setText("Память почти заполнена. Во вкладке режимов можно выбрать приложения для закрытия или выгрузить ИИ." if data['ram'] > 85 else "Высокая загрузка процессора. Во вкладке режимов можно снизить приоритет фоновых приложений." if data['cpu'] > 85 else "Ресурсы доступны. Дополнительная оптимизация сейчас может не дать заметного ускорения.")
        self.hardware.setPlainText(data["hardware"] + f"\nОперативная память: {size_text(data['total'])}")
        checked = self.selected()
        self.processes.setRowCount(len(data["processes"]))
        for row, (pid, name, cpu, memory) in enumerate(data["processes"]):
            item = W.QTableWidgetItem(name)
            item.setFlags(item.flags() | C.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(C.Qt.CheckState.Checked if pid in checked else C.Qt.CheckState.Unchecked)
            self.processes.setItem(row, 0, item)
            for column, value in enumerate((pid, f"{cpu:.1f}", size_text(memory)), 1):
                self.processes.setItem(row, column, W.QTableWidgetItem(str(value)))

    def selected(self):
        return {int(self.processes.item(row, 1).text()) for row in range(self.processes.rowCount()) if self.processes.item(row, 0) and self.processes.item(row, 0).checkState() == C.Qt.CheckState.Checked}

    def disk_usage(self):
        if self.drives.currentData():
            try:
                usage = psutil.disk_usage(self.drives.currentData())
                self.disk_status.setText(f"Занято {size_text(usage.used)} · свободно {size_text(usage.free)} · всего {size_text(usage.total)}")
                self.disk_bar.parts = [("Занято", usage.used), ("Свободно", usage.free)]; self.disk_bar.update()
            except OSError as exc:
                self.disk_status.setText(str(exc))

    def start_scan(self):
        if self.scan_thread and self.scan_thread.is_alive() or not self.drives.currentData():
            return
        self.cancel.clear(); self.scan_button.setEnabled(False); self.drives.setEnabled(False)
        self.scan_progress.loading(True, "Анализирую файлы на диске")
        self.scan_thread = threading.Thread(target=self.scan, args=(self.drives.currentData(),), daemon=True)
        self.scan_thread.start()

    def scan(self, root):
        try:
            scan_disk(root, self.cancel, self.scanResult.emit)
        finally:
            self.scanResult.emit({}, -1, 0, False)

    def update_disk(self, totals, count, denied, complete):
        if count == -1:
            self.scan_progress.loading(False)
            self.scan_button.setEnabled(True); self.drives.setEnabled(True)
            if self.cancel.is_set():
                self.disk_status.setText(self.disk_status.text() + " · отменено, показан частичный результат")
            return
        try:
            usage = psutil.disk_usage(self.drives.currentData())
        except OSError:
            self.cancel.set(); self.disk_status.setText("Диск отключён или недоступен."); return
        parts = sorted(totals.items(), key=lambda x: -x[1])
        parts += [("Не классифицировано / недоступно", max(0, usage.used - sum(totals.values()))), ("Свободно", usage.free)]
        self.disk_bar.parts = parts; self.disk_bar.update()
        self.categories.setHtml("<br>".join(f'<span style="color:{COLORS[i % len(COLORS)]}">●</span> {name}: <b>{size_text(value)}</b>' for i, (name, value) in enumerate(parts)))
        self.disk_status.setText(f"{'Анализ завершён' if complete else 'Анализирую…'} · файлов {count:,} · пропущено {denied} · свободно {size_text(usage.free)}")

    def run_job(self, function):
        if self.busy:
            self.message.emit("Дождитесь завершения настройки ПК."); return
        self.busy = True; self.job_status.setText("Применяю настройки…")
        self.job_progress.loading(True, "Применяю настройки ПК")
        def work():
            try:
                text = function()
            except Exception as exc:
                text = "Не удалось применить все настройки: " + str(exc) + ". Можно нажать «Вернуть настройки»."
            self.jobDone.emit(text)
        threading.Thread(target=work, daemon=True, name="pc-profile").start()

    def job_finished(self, text):
        self.job_progress.loading(False)
        self.busy = False; self.job_status.setText(text); self.message.emit(text)

    def profile(self, mode):
        self.cancel.set()
        self.run_job(lambda: self.optimizer.profile(mode))

    def optimize(self):
        selected = self.selected()
        self.run_job(lambda: self.optimizer.lower(selected or None))

    def close_selected(self):
        selected = self.selected()
        if not selected:
            self.message.emit("Сначала отметьте приложения в таблице."); return
        names = [self.processes.item(row, 0).text() for row in range(self.processes.rowCount()) if int(self.processes.item(row, 1).text()) in selected]
        answer = W.QMessageBox.question(self, "Закрыть выбранные приложения?", "Будет отправлен обычный запрос закрытия:\n" + "\n".join(dict.fromkeys(names)) + "\n\nПриложения могут запросить сохранение документов.")
        if answer == W.QMessageBox.StandardButton.Yes:
            self.run_job(lambda: self.optimizer.close_selected(selected))

    def close_services(self):
        self.cancel.set(); self.metrics.cancel.set()
