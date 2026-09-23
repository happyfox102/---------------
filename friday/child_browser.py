"""Opt-in child browser; no capture of personal browser sessions."""
from .qt import QtCore as C, QtWidgets as W, Signal, BINDING
if BINDING == 'PyQt6':
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor, QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
else:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
from .child_policy import decision, review_query, schedule_allowed
from .design import button
from urllib.parse import quote, urlsplit, parse_qs
import threading
import time


class Filter(QWebEngineUrlRequestInterceptor):
    denied = Signal(str, str)
    def __init__(self, config, parent):
        super().__init__(parent)
        self.config = config
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if url == 'about:blank':
            return
        allowed, reason = decision(url, self.config)
        if not allowed:
            info.block(True)
            # Report navigations only, not hundreds of blocked trackers.
            if info.resourceType() == info.ResourceType.ResourceTypeMainFrame:
                self.denied.emit(info.requestUrl().host(), reason)


class Page(QWebEnginePage):
    navigated = Signal(str)
    def __init__(self, profile, config, parent):
        super().__init__(profile, parent)
        self.config = config
    def acceptNavigationRequest(self, url, kind, main):
        value = url.toString()
        if value == 'about:blank':
            return True
        allowed, _ = decision(value, self.config)
        if main:
            self.navigated.emit(value)
        return allowed
    def createWindow(self, kind):
        return None
    def chooseFiles(self, mode, old_files, mime_types):
        return []


class ChildBrowser(W.QMainWindow):
    notice = Signal(str)
    reviewed = Signal(str)
    def __init__(self, service, config, parent=None):
        super().__init__(parent)
        self.service, self.config = service, dict(config)
        self.setWindowTitle('Пятница · детский браузер · контроль включён')
        self.resize(1050, 750)
        self.review_busy = False
        self.last_review = 0
        self.last_denied = None
        body = W.QWidget(); layout = W.QVBoxLayout(body); self.setCentralWidget(body)
        self.status = W.QLabel('Доступны только одобренные родителем HTTPS-сайты. Новые окна и загрузки запрещены.')
        self.status.setWordWrap(True); layout.addWidget(self.status)
        row = W.QHBoxLayout()
        self.address = W.QLineEdit(); self.address.setPlaceholderText('Адрес сайта или поисковый запрос')
        self.address.returnPressed.connect(self.navigate); row.addWidget(self.address)
        go = W.QPushButton('Перейти'); button(go,'search',icon_only=True); go.clicked.connect(self.navigate); row.addWidget(go)
        layout.addLayout(row)
        self.view = QWebEngineView(); layout.addWidget(self.view,1)
        self.profile = QWebEngineProfile(self)
        self.filter = Filter(self.config, self.profile)
        self.filter.denied.connect(self.denied)
        self.profile.setUrlRequestInterceptor(self.filter)
        self.profile.downloadRequested.connect(self.reject_download)
        self.page = Page(self.profile, self.config, self.view)
        self.page.navigated.connect(self.navigation)
        self.view.setPage(self.page)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        self.page.permissionRequested.connect(lambda permission: permission.deny())
        self.reviewed.connect(self.review_finished)
        self.clock = C.QTimer(self); self.clock.setInterval(15000); self.clock.timeout.connect(self.check_time); self.clock.start()

    def reject_download(self, download):
        download.cancel()
        self.denied('', 'Загрузка файлов запрещена')

    def denied(self, host, reason):
        current = (host, reason)
        self.status.setText('Доступ запрещён: ' + reason)
        if current != self.last_denied:
            self.last_denied = current
            self.service.event('browser_block', outcome='blocked', reason=host + ' · ' + reason)
            self.notice.emit('Детский браузер: ' + reason)

    def navigate(self):
        text = self.address.text().strip()
        if not text:
            return
        url = text if '://' in text else 'https://' + text if '.' in text and ' ' not in text else 'https://www.bing.com/search?adlt=strict&q=' + quote(text[:500])
        allowed, reason = decision(url, self.config)
        if not allowed:
            self.denied(urlsplit(url).hostname or '', reason)
            return
        self.view.setUrl(C.QUrl(url))

    def navigation(self, url):
        allowed, reason = decision(url, self.config)
        host = urlsplit(url).hostname or ''
        if not allowed:
            self.denied(host, reason)
            return
        self.last_denied = None
        self.service.event('browser_visit', outcome='requested', reason=host)
        values = parse_qs(urlsplit(url).query)
        query = (values.get('q') or values.get('text') or [''])[0]
        if query and self.config.get('security_ai_review') and not self.review_busy and time.monotonic() - self.last_review > 60:
            self.review_busy = True; self.last_review = time.monotonic()
            def work():
                try:
                    result = review_query(query, self.config)
                except Exception:
                    result = 'ИИ недоступен; оценка запроса не выполнена. Правила сайтов продолжают работать.'
                self.reviewed.emit(result)
            threading.Thread(target=work,daemon=True,name='child-query-review').start()

    def review_finished(self, result):
        self.review_busy = False
        self.service.event('ai_review', outcome='observed', reason=result[:2000])
        self.notice.emit('Оценка ИИ (не заключение): ' + result[:400])

    def check_time(self):
        if not schedule_allowed(self.config.get('security_parent_start',''), self.config.get('security_parent_end','')):
            self.view.stop()
            self.view.setUrl(C.QUrl('about:blank'))
            self.denied('', 'Время доступа истекло')

    def closeEvent(self, event):
        self.view.stop(); self.view.setUrl(C.QUrl('about:blank')); self.clock.stop()
        super().closeEvent(event)
