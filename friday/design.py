"""Shared palette, typography and line icons for every application page."""
from functools import lru_cache
from .qt import QtCore as C, QtGui as G, QtWidgets as W
try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:
    from PyQt6.QtSvg import QSvgRenderer

DEFAULTS = {"background": "#10151f", "accent": "#73dfc1", "font": "Segoe UI", "size": 14, "compact": False, "sidebar": False}
GLYPHS = {
    "plus": '<path d="M12 4v16M4 12h16"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M10 3h4l1 3 3 1 3 3v4l-3 1-1 3-3 3h-4l-1-3-3-1-3-3v-4l3-1 1-3z"/>',
    "camera": '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="m8 6 2-3h4l2 3"/><circle cx="12" cy="13" r="4"/>',
    "bulb": '<path d="M8 16c0-3-3-3-3-7a7 7 0 0 1 14 0c0 4-3 4-3 7M8 17h8M9 20h6M11 23h2"/>',
    "mic": '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',
    "send": '<path d="m3 3 19 9-19 9 4-9zM7 12h15"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="3"/>',
    "radio": '<path d="M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14M8 8a6 6 0 0 0 0 8M16 8a6 6 0 0 1 0 8"/><circle cx="12" cy="12" r="1"/>',
    "chat": '<path d="M5 3h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H9l-6 3V5a2 2 0 0 1 2-2zM7 8h10M7 12h6"/>',
    "file": '<path d="M5 2h9l5 5v15H5zM14 2v6h5M8 12h8M8 16h6"/>',
    "folder": '<path d="M3 5h6l2 3h10v12H3z"/>',
    "pc": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 17v4M7 22h10"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9 8a3 3 0 0 1 6 0c0 3-3 2-3 5M12 17v1"/>',
    "chart": '<path d="M3 3v18h18M6 15l4-6 4 3 5-7"/>',
    "disk": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 14h18M7 17h1M11 17h1"/>',
    "game": '<path d="M7 7h10c3 0 5 5 5 10s-4 2-6-1H8c-2 3-6 6-6 1s2-10 5-10zM7 10v5M4.5 12.5h5M16 11h.1M19 14h.1"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M3 13h18M10 13v3h4v-3"/>',
    "leaf": '<path d="M20 3C8 2 2 7 4 15s16 7 16-12zM4 21 16 9"/>',
    "bolt": '<path d="m13 2-9 12h7l-1 8 10-13h-8z"/>',
    "restore": '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7"/>',
    "pause": '<path d="M8 4v16M16 4v16"/>',
    "record": '<circle cx="12" cy="12" r="8"/>',
    "palette": '<path d="M12 2a10 10 0 1 0 0 20h2c2 0 3-2 1-4-2-2 0-4 2-4h3c3-6-2-12-8-12z"/><circle cx="7" cy="8" r="1"/><circle cx="12" cy="6" r="1"/><circle cx="17" cy="8" r="1"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M6 6l1 16h10l1-16M10 10v8M14 10v8"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "tray": '<path d="M3 14v6h18v-6M12 2v13M7 10l5 5 5-5"/>',
    "search": '<circle cx="10" cy="10" r="7"/><path d="m15 15 7 7"/>',
    "speaker": '<path d="M4 10h4l5-4v12l-5-4H4zM17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/>',
    "vision": '<path d="M2 12s3-6 10-6 10 6 10 6-3 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/>',
    "ai": '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/><circle cx="12" cy="12" r="5"/>',
    "marketplace": '<path d="M4 10h16v10H4zM3 10l2-6h14l2 6M8 10v2a4 4 0 0 0 8 0v-2"/>',
    "skills": '<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',
    "profile": '<circle cx="12" cy="8" r="3"/><path d="M5 21a7 7 0 0 1 14 0"/>',
    "success": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "add": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
}


def settings(config):
    result = dict(DEFAULTS)
    result.update(config.get("design", {}))
    for name in ("background", "accent"):
        if not G.QColor(result[name]).isValid():
            result[name] = DEFAULTS[name]
    if result["font"] not in ("Segoe UI", "Arial", "Calibri"):
        result["font"] = DEFAULTS["font"]
    result["size"] = max(12, min(18, int(result["size"])))
    return result


def palette(config):
    design = settings(config)
    bg = G.QColor(design["background"])
    def luminance(color):
        channels = [v / 12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in (color.redF(), color.greenF(), color.blueF())]
        return sum(v*w for v,w in zip(channels, (.2126,.7152,.0722)))
    light = luminance(bg) > .179
    fg = G.QColor("#172233" if light else "#e7edf6")
    def mix(amount):
        return G.QColor(*[round(bg.getRgb()[i]*(1-amount)+fg.getRgb()[i]*amount) for i in range(3)]).name()
    return dict(design, bg=bg.name(), fg=fg.name(), surface=mix(.045), raised=mix(.085), border=mix(.18), muted=mix(.65), primary_text="#102720" if luminance(G.QColor(design["accent"])) > .179 else "#ffffff")


def stylesheet(config):
    p = palette(config); pad = 6 if p['compact'] else 10
    return f'''
    QWidget {{background:{p['bg']}; color:{p['fg']};font-family:'{p['font']}';font-size:{p['size']}px;}}
    QLabel {{background:transparent;}}
    QLabel#brand {{font-size:25px;font-weight:600;}}
    QLabel#muted {{color:{p['muted']};}}
    QLabel#status {{color:{p['muted']};padding:4px 0;}}
    QLabel#sectionTitle {{font-size:18px;font-weight:600;}}
    QLabel#detailCard,QFrame#card {{background:{p['surface']};border:1px solid {p['border']};border-radius:12px;padding:12px;}}
    QPushButton,QToolButton {{background:{p['surface']};border:1px solid {p['border']};border-radius:9px;padding:{pad}px 12px;}}
    QPushButton:hover,QToolButton:hover {{background:{p['raised']};border-color:{p['accent']};}}
    QPushButton:pressed {{background:{p['border']};}}
    QPushButton:disabled {{color:{p['muted']};border-color:{p['raised']};}}
    QPushButton#primary {{background:{p['accent']};color:{p['primary_text']};border-color:{p['accent']};font-weight:600;}}
    QLineEdit,QTextEdit,QTextBrowser,QComboBox,QSpinBox,QListWidget,QTableWidget {{background:{p['surface']};border:1px solid {p['border']};border-radius:9px;padding:8px;selection-background-color:{p['border']};}}
    QLineEdit:focus,QTextEdit:focus,QComboBox:focus,QPushButton:focus {{border-color:{p['accent']};}}
    QComboBox::drop-down {{border:0;width:24px;}}
    QTabWidget::pane {{border:0;padding-top:10px;}}
    QTabBar::tab {{background:transparent;color:{p['muted']};padding:{pad+2}px 13px;border-bottom:2px solid transparent;}}
    QTabBar::tab:selected {{color:{p['fg']};border-bottom:2px solid {p['accent']};}}
    QTabBar::tab:hover {{background:{p['surface']};}}
    QHeaderView::section {{background:{p['raised']};border:0;padding:8px;color:{p['muted']};}}
    QTableWidget {{gridline-color:{p['border']};}}
    QCheckBox {{spacing:8px;}}
    QCheckBox::indicator {{width:17px;height:17px;border:1px solid {p['border']};border-radius:5px;background:{p['surface']};}}
    QCheckBox::indicator:checked {{background:{p['accent']};border-color:{p['accent']};}}
    QProgressBar {{background:{p['raised']};border:0;border-radius:3px;min-height:5px;max-height:5px;}}
    QProgressBar::chunk {{background:{p['accent']};border-radius:3px;}}
    QScrollBar:vertical {{background:transparent;width:8px;}}
    QScrollBar::handle:vertical {{background:{p['border']};min-height:30px;border-radius:4px;}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
    QSlider::groove:horizontal {{height:5px;background:{p['border']};border-radius:2px;}}
    QSlider::handle:horizontal {{width:16px;margin:-6px 0;border-radius:8px;background:{p['accent']};}}
    QToolTip {{background:{p['raised']};color:{p['fg']};border:1px solid {p['border']};padding:5px;}}
    '''


@lru_cache(maxsize=256)
def glyph(name, color="#aab8ca"):
    data = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{GLYPHS.get(name, GLYPHS["file"])}</g></svg>'
    pix = G.QPixmap(48, 48); pix.fill(C.Qt.GlobalColor.transparent)
    painter = G.QPainter(pix); QSvgRenderer(C.QByteArray(data.encode())).render(painter); painter.end()
    pix.setDevicePixelRatio(2)
    return G.QIcon(pix)


def button(widget, name, label=None, icon_only=False):
    original = widget.accessibleName() or widget.text()
    widget.setAccessibleName(original)
    if not widget.toolTip():
        widget.setToolTip(original)
    widget.setProperty("glyph", name)
    widget.setProperty("iconOnly", icon_only)
    widget.setIcon(glyph(name))
    widget.setIconSize(C.QSize(20, 20))
    if label is not None:
        widget.setText(label)
    if icon_only:
        widget.setText(""); widget.setFixedWidth(44)


def apply_theme(app, config):
    p = palette(config)
    app.setStyleSheet(stylesheet(config))
    app.setProperty("fridayPalette", p)
    for widget in app.allWidgets():
        name = widget.property("glyph")
        if name and isinstance(widget, W.QPushButton):
            widget.setIcon(glyph(name, p['primary_text'] if widget.objectName() == 'primary' else p['fg']))
        widget.update()


def current_palette():
    app = W.QApplication.instance()
    return (app.property("fridayPalette") if app else None) or palette({})


class LoadingBar(W.QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False); self.setRange(0, 0); self.hide()
        self.setAccessibleName("Выполнение операции")

    def loading(self, active, text="Загрузка"):
        self.setToolTip(text); self.setAccessibleName(text); self.setVisible(bool(active))


class Appearance(W.QWidget):
    def __init__(self, config):
        super().__init__()
        self.original = dict(config); self.value = settings(config)
        layout = W.QFormLayout(self); layout.setSpacing(18)
        self.preset = W.QComboBox(); self.preset.addItems(["Полночь", "Графит", "Светлая", "Свой цвет"])
        self.preset.setCurrentIndex(3)
        self.preset.currentIndexChanged.connect(self.choose_preset); layout.addRow("Тема", self.preset)
        self.bg = W.QPushButton("Цвет фона"); button(self.bg, "palette"); self.bg.clicked.connect(lambda: self.choose_color("background")); layout.addRow("Фон", self.bg)
        self.accent = W.QPushButton("Акцентный цвет"); button(self.accent, "palette"); self.accent.clicked.connect(lambda: self.choose_color("accent")); layout.addRow("Акцент", self.accent)
        self.font = W.QComboBox(); self.font.addItems(["Segoe UI", "Arial", "Calibri"]); self.font.setCurrentText(self.value['font']); self.font.currentTextChanged.connect(self.preview); layout.addRow("Шрифт", self.font)
        self.scale = W.QSlider(C.Qt.Orientation.Horizontal); self.scale.setRange(12, 18); self.scale.setValue(self.value['size']); self.scale.valueChanged.connect(self.preview); layout.addRow("Размер текста", self.scale)
        self.compact = W.QCheckBox("Компактные отступы"); self.compact.setChecked(self.value['compact']); self.compact.toggled.connect(self.preview); layout.addRow(self.compact)
        self.sidebar = W.QCheckBox("Показывать панель быстрых действий"); self.sidebar.setChecked(self.value['sidebar']); self.sidebar.toggled.connect(self.preview); layout.addRow(self.sidebar)
        reset = W.QPushButton("Сбросить оформление"); button(reset, "restore"); reset.clicked.connect(self.reset); layout.addRow(reset)
        note = W.QLabel("Предпросмотр сразу. «Отмена» вернёт прежний вид."); note.setObjectName("muted"); layout.addRow(note)

    def choose_preset(self, index):
        if index < 3:
            self.value['background'] = ['#10151f', '#202329', '#f4f6fa'][index]; self.preview()

    def choose_color(self, name):
        color = W.QColorDialog.getColor(G.QColor(self.value[name]), self, "Выберите цвет")
        if color.isValid():
            self.value[name] = color.name(); self.preview()

    def config(self):
        return dict(self.value, font=self.font.currentText(), size=self.scale.value(), compact=self.compact.isChecked(), sidebar=self.sidebar.isChecked())

    def preview(self, *_):
        self.value = self.config()
        self.bg.setText(self.value['background']); self.accent.setText(self.value['accent'])
        apply_theme(W.QApplication.instance(), dict(self.original, design=self.value))

    def reset(self):
        self.value = dict(DEFAULTS)
        self.font.setCurrentText(DEFAULTS['font']); self.scale.setValue(DEFAULTS['size'])
        self.compact.setChecked(False); self.sidebar.setChecked(False); self.preview()
