"""Visual integration check, also runnable inside the frozen application."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from .qt import QtWidgets as W, QtGui as G
from .storage import Store
from .paths import ROOT
from .design import apply_theme, palette
from .guide import HELP_ASSETS, CHAPTERS
from .ui import Window, Settings


def run():
    output = ROOT/'artifacts'; output.mkdir(exist_ok=True)
    report = {}
    try:
        app = W.QApplication([]); app.setStyle('Fusion')
        for font in ('segoeui.ttf','segoeuib.ttf'):
            G.QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)); store.config.update(speak=False,search_roots=[temp],tour_seen=True)
            store.write('history.json',[{'role':'Вы','text':'Привет'},{'role':'Пятница','text':'Чем помочь?'}])
            w = Window(store); w.show(); app.processEvents()
            assert w.dialogue.toPlainText().count('Чем помочь?') == 1
            assert not w.quick_panel.isVisible()
            w.tabs.setCurrentWidget(w.market_page); app.processEvents()
            w.market_page.change('browser','disable')
            assert 'browser.search' not in w.engine.operator.registry.available()
            w.market_page.change('browser','uninstall')
            assert 'browser' not in w.engine.operator.skills.state
            w.market_page.change('browser','install')
            assert 'browser.search' in w.engine.operator.registry.available()
            w.market_page.search.setText('Browser'); app.processEvents()
            w.grab().save(str(output/'marketplace-functional.png'))
            w.tabs.setCurrentWidget(w.dialogue)
            w.render_message('Пятница','Источник: https://example.org/test?q=a&lang=ru')
            assert 'https://example.org/test?q=a&amp;lang=ru' in w.dialogue.toHtml()
            report['skills_lifecycle']=True
            w.feature_action('vpn'); assert w.tabs.currentWidget() is w.vpn
            assert w.vpn.service.client_path({'client': 'AmneziaVPN'}) is None or w.vpn.service.client_path({'client': 'AmneziaVPN'}).is_file()
            w.vpn.key.setPlainText('file:///C:/invalid'); w.vpn.key_name.setText('Тест')
            w.vpn.import_key(); assert not w.vpn.busy
            assert not w.vpn.service.profiles()
            w.vpn.key.clear(); report['vpn_panel']=True
            required = {name for _,_,steps in CHAPTERS for _,_,name in steps}
            assert all(not G.QPixmap(str(HELP_ASSETS/(name+'.png'))).isNull() for name in required)
            report['help_images'] = len(required)
            def devices(dialog):
                dialog.devicesFound.emit([],[])
            with patch.object(Settings,'load_devices',devices):
                s = Settings(store,w); s.show(); s.device_thread.join(2); app.processEvents()
                s.tabs.setCurrentIndex(2); app.processEvents()
                assert s.cloud.values()['ai_provider'] == 'ollama'
                assert s.cloud.key.echoMode() == W.QLineEdit.EchoMode.Password
                report['openai_settings']=True
                s.tabs.setCurrentIndex(3); s.appearance.choose_preset(2); app.processEvents()
                assert app.property('fridayPalette')['fg'] == '#172233'
                w.grab().save(str(output/'design-light.png'))
                s.grab().save(str(output/'design-settings.png'))
                s.reject(); assert app.property('fridayPalette')['bg'] == '#10151f'
                s = Settings(store,w); s.show(); s.device_thread.join(2); app.processEvents()
                s.tabs.setCurrentIndex(4); app.processEvents()
                s.grab().save(str(output/'design-help.png'))
                for chapter in range(len(CHAPTERS)):
                    s.help_page.menu.setCurrentRow(chapter); app.processEvents()
                    assert s.help_page.scroll.widget() is not None
                s.appearance.value['accent']='#7ea8ff'; s.save()
                assert Store(Path(temp)).config['design']['accent']=='#7ea8ff'
            w.start_tour(); app.processEvents()
            w.grab().save(str(output/'design-tour.png'))
            for step in range(7):
                assert w.tour.index == step
                assert w.tour.rect().contains(w.tour.card.geometry())
                w.tour.move_step(1); app.processEvents()
            assert w.tour is None and store.config['tour_seen']
            report['tour_steps'] = 7
            w.resize(840,600); w.start_tour(); app.processEvents()
            for step in range(7):
                assert w.tour.rect().contains(w.tour.card.geometry())
                w.tour.move_step(1); app.processEvents()
            w.busy.set(); w.update_activity(); assert not w.activity.isHidden()
            w.busy.clear(); w.pc.scan_progress.loading(True); w.pc.update_disk({},-1,0,False)
            assert w.pc.scan_progress.isHidden()
            w.pc.job_progress.loading(True); w.pc.job_finished('Готово')
            assert w.pc.job_progress.isHidden()
            w.feature_action('record_open'); assert w.recording.progress.isHidden()
            assert not w.recording.stop_button.isEnabled()
            w.recording.progress.loading(True); w.recording.fail('Учебная ошибка')
            # No source was opened by this check.
            w.close(); w.engine.file_index.thread.join(10); w.speaker.thread.join(3); app.processEvents()
            report['ok'] = True
    except Exception:
        import traceback
        report['error'] = traceback.format_exc(); report['ok'] = False
    (output/'design-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['ok'] else 1
