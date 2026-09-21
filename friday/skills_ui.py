"""Local capability catalog backed by the actual registry."""
from .qt import QtWidgets as W
from .design import button, apply_theme
from .operator import CATALOG


class SkillsPage(W.QWidget):
    def __init__(self, window, mine=False):
        super().__init__()
        self.window, self.mine = window, mine
        layout=W.QVBoxLayout(self)
        row=W.QHBoxLayout(); self.search=W.QLineEdit(); self.search.setPlaceholderText('Найти способность')
        self.category=W.QComboBox(); self.category.addItems(['Все категории']+sorted({v['category'] for v in CATALOG.values()}))
        row.addWidget(self.search,1); row.addWidget(self.category); layout.addLayout(row)
        self.scroll=W.QScrollArea(); self.scroll.setWidgetResizable(True); layout.addWidget(self.scroll)
        self.search.textChanged.connect(self.refresh); self.category.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self,*_):
        page=W.QWidget(); layout=W.QVBoxLayout(page)
        for key,value in CATALOG.items():
            state=self.window.engine.operator.skills.state.get(key,{})
            installed,enabled=state.get('installed',False),state.get('enabled',False)
            if self.mine and not installed:
                continue
            if self.search.text().casefold() not in (value['name']+' '+value['description']).casefold():
                continue
            if self.category.currentIndex() and self.category.currentText()!=value['category']:
                continue
            card=W.QFrame(); card.setObjectName('card'); box=W.QVBoxLayout(card)
            row=W.QHBoxLayout(); title=W.QLabel(value['name']); title.setObjectName('sectionTitle'); row.addWidget(title,1)
            status=W.QLabel('Включён' if installed and enabled else 'Выключен' if installed else 'В локальном каталоге'); status.setObjectName('muted'); row.addWidget(status); box.addLayout(row)
            desc=W.QLabel(value['description']); desc.setWordWrap(True); box.addWidget(desc)
            row=W.QHBoxLayout(); action='disable' if installed and enabled else 'enable' if installed else 'install'
            toggle=W.QPushButton({'disable':'Выключить','enable':'Включить','install':'Установить'}[action]); button(toggle,value['icon'])
            toggle.clicked.connect(lambda checked=False,k=key,a=action:self.change(k,a)); row.addWidget(toggle)
            if installed:
                remove=W.QPushButton('Удалить'); button(remove,'trash',icon_only=True); remove.clicked.connect(lambda checked=False,k=key:self.change(k,'uninstall')); row.addWidget(remove)
            row.addStretch(); box.addLayout(row); layout.addWidget(card)
        note=W.QLabel('Локальные пакеты: установка подключает инструменты к ИИ.\nНастройки навыков не удаляют файлы и обычные голосовые команды.'); note.setWordWrap(True); note.setObjectName('muted'); layout.addWidget(note); layout.addStretch()
        old=self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(page)

    def change(self,key,action):
        if self.window.busy.is_set():
            self.window.show_error('Сначала остановите текущую задачу.'); return
        self.window.engine.operator.skills.change(key,action)
        for page in (self.window.skills_page,self.window.market_page):
            page.refresh()
        apply_theme(W.QApplication.instance(),self.window.store.config)
