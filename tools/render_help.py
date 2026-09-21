"""Render real widgets with safe demonstration data; never capture desktop/camera."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from friday.qt import QtCore as C, QtGui as G, QtWidgets as W
from friday.ui import Window, Settings
from friday.storage import Store
from friday.design import apply_theme
from friday.guide import CHAPTERS, HELP_ASSETS


def main():
    app = W.QApplication([]); app.setStyle('Fusion')
    for font in ('segoeui.ttf', 'segoeuib.ttf'):
        G.QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
    HELP_ASSETS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp)); store.config.update(speak=False, search_roots=[temp], tour_seen=True)
        w = Window(store); w.resize(1100, 790); w.show()
        w.activity_timer.stop(); w.activity.loading(False)
        def shot(name, widget=w):
            app.processEvents(); app.processEvents()
            assert widget.grab().save(str(HELP_ASSETS / (name+'.png')))
        def dialogue(name, question, answer):
            w.tabs.setCurrentWidget(w.dialogue); w.dialogue.clear()
            w.append('Вы', question, save=False); w.append('Пятница', answer, save=False)
            w.status.setText('Учебный пример · действия не выполняются')
            shot(name)
        dialogue('dialog', 'который час', 'Сейчас 14:30.')
        shot('overview')
        w.status.setText('Слушаю… · учебный пример'); w.mic_button.setEnabled(False)
        w.input.setPlaceholderText('Произнесите команду после сигнала'); shot('voice')
        w.mic_button.setEnabled(True); w.input.setPlaceholderText('Напишите команду или вопрос ИИ…')
        examples = [
            ('apps','открой мне диспетчер задач','Открываю Диспетчер задач.'),
            ('files','открой папку','Как называется папка?'),
            ('documents','создай Word Отчёт','Создан документ Отчёт.docx в папке data/documents.'),
            ('excel','запиши 1500 в B3','Записано в B3. Книга сохранена.'),
            ('notes','покажи заметки','1. Купить молоко\n2. Подготовить презентацию'),
            ('reminders','через 20 минут напомни сделать перерыв','Напомню в 14:50: сделать перерыв. Помощник должен оставаться запущенным.'),
            ('screenshots','сделай скриншот приложения','Снимок активного окна сохранён в data/screenshots.'),
            ('windows','яркость 50','Яркость: 50%.'),
            ('ai','Объясни, что такое Python','Python — язык программирования. На нём можно создавать приложения, обрабатывать данные и автоматизировать повседневные задачи.'),
        ]
        for example in examples:
            dialogue(*example)
        dialogue('ocr', 'Прочитать изображение · значок глаза', 'Учебный пример OCR: План на неделю. Подготовить отчёт.')
        w.tabs.setCurrentWidget(w.skills_page); shot('skills')
        w.tabs.setCurrentWidget(w.vpn); w.vpn.timer.stop(); shot('vpn')
        vpn_tabs = w.vpn.findChild(W.QTabWidget)
        vpn_tabs.setCurrentIndex(1); w.vpn.server_name.setText('Учебный VPN'); w.vpn.server.setText('vpn.example.com'); shot('vpn_server')
        w.draft.setPlainText('План на неделю\n\nПодготовить отчёт.\nОбновить презентацию.\nПроверить результаты.'); w.tabs.setCurrentWidget(w.draft); shot('dictation')
        pc = w.pc; w.tabs.setCurrentWidget(pc)
        pc.update_metrics(dict(cpu=24, ram=42, gpu=12, used=6.7*1024**3, total=16*1024**3,
            battery=(85,True), disk_rate=8*1024**2, download=2*1024**2, frequency=2600,
            hardware='Учебный компьютер\n\nПроцессор: 4 ядра / 8 потоков\nВидеокарта: встроенная графика\nСистема: Windows 11, 64-разрядная',
            processes=[(120,'Браузер',4.2,640*1024**2),(240,'Текстовый редактор',.8,180*1024**2),(360,'Музыкальный плеер',.4,96*1024**2)]))
        for i in range(40):
            for key, gauge in pc.gauges.items():
                gauge.sample({'cpu':24,'ram':42,'gpu':12}[key] + (i%7-3))
        pc.show_page('overview'); shot('pc')
        pc.show_page('hardware'); shot('hardware')
        pc.show_page('modes'); shot('modes')
        pc.show_page('disk'); pc.disk_status.setText('Учебный пример · занято 320 ГБ · свободно 180 ГБ')
        pc.disk_bar.parts = [('Программы',100),('Игры',120),('Фото',40),('Документы',20),('Прочее',40),('Свободно',180)]
        pc.categories.setPlainText('\n'.join(f'{name}    {size} ГБ' for name,size in pc.disk_bar.parts)); shot('storage')
        w.feature_action('record_open'); r = w.recording
        r.camera_choice.clear(); r.camera_choice.addItem('Камера · учебный пример')
        r.audio_choice.clear(); r.audio_choice.addItem('Микрофон · учебный пример')
        # A screenshot of this application, plus an illustrated camera placeholder.
        preview = G.QPixmap(str(HELP_ASSETS/'pc.png')).scaled(800,450,C.Qt.AspectRatioMode.IgnoreAspectRatio)
        painter = G.QPainter(preview); painter.fillRect(610,325,175,110,G.QColor('#28354a'))
        painter.setPen(G.QColor('#e7edf6')); painter.drawText(C.QRect(610,325,175,110),C.Qt.AlignmentFlag.AlignCenter,'Камера\nУчебный пример'); painter.end()
        r.preview.setPixmap(preview); r.status.setText('Пример предпросмотра · запись не запущена'); shot('recording')
        def demo_devices(dialog):
            dialog.devicesFound.emit([(0,'Микрофон · учебный пример')], [('demo','Русский голос Windows')])
        with patch.object(Settings, 'load_devices', demo_devices):
            s = Settings(store,w); s.show(); s.device_thread.join(3); app.processEvents()
            s.roots.setPlainText('C:/Users/Пользователь/Documents\nD:/Проекты')
            s.vosk.setText('models/vosk-model-small-ru-0.22')
            for index,name in ((0,'settings_voice'),(1,'settings_files'),(2,'settings_ai'),(3,'design')):
                s.tabs.setCurrentIndex(index); shot(name,s)
            s.reject()
        required = {name for _,_,steps in CHAPTERS for _,_,name in steps}
        assert all((HELP_ASSETS/(name+'.png')).is_file() for name in required)
        w.close(); w.engine.file_index.thread.join(10); w.speaker.thread.join(3)
        app.processEvents()
    print(f'Rendered {len(required)} illustrated help images.')

if __name__ == '__main__':
    main()
