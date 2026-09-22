"""Native Qt message bubbles; no unsupported HTML layout properties."""
from .qt import QtWidgets as W, QtCore as C

class ChatView(W.QScrollArea):
    anchorClicked = C.pyqtSignal(object) if hasattr(C, 'pyqtSignal') else C.Signal(object)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.body = W.QWidget()
        self.rows = W.QVBoxLayout(self.body)
        self.rows.setContentsMargins(16, 16, 16, 16)
        self.rows.setSpacing(12)
        self.rows.addStretch()
        self.setWidget(self.body)
        self._texts = []

    def setOpenExternalLinks(self, enabled): pass

    def clear(self):
        self._texts.clear()
        while self.rows.count() > 1:
            item = self.rows.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def append(self, text):
        self.add_message('Пятница', text, '')

    def toPlainText(self):
        return '\n'.join(self._texts)

    def add_message(self, role, content, stamp):
        self._texts.append(content)
        outgoing = role == 'Вы'
        row = W.QWidget()
        layout = W.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        bubble = W.QFrame()
        bubble.setObjectName('messageBubble')
        bubble.setMaximumWidth(620)
        bg = '#285575' if outgoing else '#202e3a'
        bubble.setStyleSheet(f'QFrame#messageBubble {{background:{bg};border:1px solid #3b5266;border-radius:16px;}} QLabel {{border:0;background:transparent;color:#edf4fa;font-size:16px;}}')
        inside = W.QVBoxLayout(bubble)
        inside.setContentsMargins(14, 10, 14, 8)
        label = W.QLabel(content)
        label.setWordWrap(True)
        label.setTextInteractionFlags(C.Qt.TextInteractionFlag.TextBrowserInteraction)
        label.linkActivated.connect(lambda url: self.anchorClicked.emit(C.QUrl(url)))
        inside.addWidget(label)
        time = W.QLabel(stamp)
        time.setStyleSheet('color:#afc0ce;font-size:11px;')
        time.setAlignment(C.Qt.AlignmentFlag.AlignRight)
        inside.addWidget(time)
        if outgoing: layout.addStretch(1)
        layout.addWidget(bubble, 4)
        if not outgoing: layout.addStretch(1)
        self.rows.insertWidget(self.rows.count()-1, row)
        C.QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()))
