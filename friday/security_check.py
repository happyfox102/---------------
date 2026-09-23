"""Offline startup/idle measurement and child-browser rejection smoke test."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

from friday.qt import QApplication, Qt, QtCore as C, QtGui as G
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from friday.storage import Store
from friday.ui import Window, Settings
from friday.child_browser import ChildBrowser



def check():
    app = QApplication(['security-check'])    
    for font in ('segoeui.ttf','segoeuib.ttf'):
        G.QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/font))
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp))
        start = time.perf_counter()
        with patch('friday.security.SecurityService.defender_status', side_effect=AssertionError('Defender on startup')):
            window = Window(store)
        print('Window construction seconds:',round(time.perf_counter()-start,3),flush=True)
        assert window.pc.metrics.thread is None
        assert window.engine.file_index.thread is None
        assert not window.security.timer.isActive()
        assert window.security.service.recent() == []
        window.show(); app.processEvents()
        settings = Settings(store,window)
        settings.tabs.setCurrentWidget(settings.security_settings)
        settings.show(); app.processEvents()
        Path('artifacts').mkdir(exist_ok=True)
        settings.grab().save('artifacts/security-settings.png')
        window.security.tabs.setCurrentIndex(3); app.processEvents()
        settings.grab().save('artifacts/security-parental.png')
        settings.reject(); app.processEvents()
        assert window.security.tabs.isHidden()
        cpu = time.process_time(); wall = time.perf_counter()
        while time.perf_counter()-wall < 5:
            app.processEvents(); time.sleep(.02)
        print('Idle CPU single-core percent:',round((time.process_time()-cpu)/(time.perf_counter()-wall)*100,2),flush=True)
        print('Creating child browser',flush=True)
        C.qInstallMessageHandler(lambda kind, context, text: print('Qt:',text,flush=True))
        child = ChildBrowser(window.security.service,{'security_allowed_sites':['example.com']})
        print('Child browser created',flush=True)
        child.show(); app.processEvents()
        loads=[]
        child.view.loadFinished.connect(loads.append)
        child.view.setUrl(C.QUrl('https://blocked.invalid'))
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            app.processEvents(); time.sleep(.02)
        assert any(x['kind']=='browser_block' for x in window.security.service.recent())
        assert loads and loads[-1] is False, loads
        child.close()
        child.page.deleteLater()
        C.QCoreApplication.sendPostedEvents(None, C.QEvent.Type.DeferredDelete)
        child.deleteLater()
        C.QCoreApplication.sendPostedEvents(None, C.QEvent.Type.DeferredDelete)
        window.security.refresh_report()
        window.tabs.setCurrentWidget(window.security); app.processEvents()
        window.grab().save('artifacts/security-reports.png')
        window.quit()
        print('Security UI, idle gating and browser block: OK',flush=True)
    

def run():
    import contextlib
    import traceback
    from .paths import ROOT
    os.chdir(ROOT)
    output = ROOT / 'artifacts'
    output.mkdir(exist_ok=True)
    with (output / 'security-check.log').open('w', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                check()
                return 0
            except Exception:
                traceback.print_exc()
                return 1