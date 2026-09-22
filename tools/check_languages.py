"""Render language previews using isolated settings and no cloud calls."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tempfile import TemporaryDirectory
from unittest.mock import patch
from friday.qt import QApplication, QtGui
from friday.storage import Store
from friday.ui import Window, Settings
from friday.localization import install

app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','sylfaen.ttf'):
    QtGui.QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
with TemporaryDirectory() as temp:
    store=Store(Path(temp))
    store.config.update(speak=False, search_roots=[temp])
    window=Window(store)
    with patch.object(Settings,'load_devices'):
        settings=Settings(store,window)
    for code, expected in [('ru','Язык'),('en','Language'),('hy','Լեզու')]:
        store.config['language']=code
        install(app,store.config)
        settings.show(); app.processEvents()
        assert expected in [settings.tabs.tabText(i) for i in range(settings.tabs.count())]
        settings.grab().save(str(Path('artifacts')/f'language-{code}.png'))
    settings.close(); window.close()
    window.speaker.thread.join(2)
    window.engine.file_index.thread.join(10)
print('RU/EN/HY settings and language switching: OK')
