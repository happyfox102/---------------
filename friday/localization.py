"""UI language catalog. User content and commands are never translated."""
from .qt import QtCore as C, QtWidgets as W

LANGUAGES = {'ru': 'Русский', 'en': 'English', 'hy': 'Հայերեն'}
ROWS = [
 ('ИИ пятница','Friday AI','Ուրբաթ ԱԲ'),
 ('ИИ пятница 1.0 (бета)','Friday AI 1.0 (beta)','Ուրբաթ ԱԲ 1.0 (բետա)'),
 ('Личный помощник','Personal assistant','Անձնական օգնական'),
 ('Настройки Пятницы','Friday settings','Ուրբաթի կարգավորումներ'),
 ('Настройки','Settings','Կարգավորումներ'),('Голос','Voice','Ձայն'),
 ('Файлы','Files','Ֆայլեր'),('ИИ','AI','ԱԲ'),('Дизайн','Appearance','Արտաքին տեսք'),
 ('Справка','Help','Օգնություն'),('Чаты','Chats','Զրույցներ'),('Язык','Language','Լեզու'),
 ('Язык интерфейса','Interface language','Միջերեսի լեզու'),
 ('Сохранить','Save','Պահպանել'),('Отмена','Cancel','Չեղարկել'),
 ('Диалог','Chat','Զրույց'),('Черновик','Draft','Սևագիր'),('Команды','Commands','Հրամաններ'),
 ('Мой ПК','My PC','Իմ համակարգիչը'),('Сценарии','Workflows','Սցենարներ'),
 ('Способности','Capabilities','Հնարավորություններ'),('Marketplace','Marketplace','Գործիքների խանութ'),
 ('История чатов','Chat history','Զրույցների պատմություն'),('Новый чат','New chat','Նոր զրույց'),
 ('Поиск чатов','Search chats','Փնտրել զրույցներ'),('Новый раздел','New section','Նոր բաժին'),
 ('Название раздела:','Section name:','Բաժնի անունը՝'),('Удаление чата','Delete chat','Ջնջել զրույցը'),
 ('Удалить этот чат и его сообщения?','Delete this chat and its messages?','Ջնջե՞լ այս զրույցն ու հաղորդագրությունները։'),
 ('Расположение истории чатов','History panel position','Պատմության վահանակի դիրք'),
 ('Слева','Left','Ձախ'),('Справа','Right','Աջ'),
 ('Говорить','Speak','Խոսել'),('По имени','Wake word','Ակտիվացման բառով'),
 ('Напишите команду или вопрос ИИ…','Type a command or ask AI…','Գրեք հրաման կամ հարց տվեք ԱԲ-ին…'),
 ('Отправить','Send','Ուղարկել'),('Озвучивать ответы','Read answers aloud','Բարձրաձայն կարդալ պատասխանները'),
 ('Отвечать голосом','Voice responses','Ձայնային պատասխաններ'),
 ('Заметки','Notes','Նշումներ'),('Напоминания','Reminders','Հիշեցումներ'),
 ('Выбрать Excel…','Select Excel…','Ընտրել Excel…'),('Мои документы','My documents','Իմ փաստաթղթերը'),
 ('Папка заметок','Notes folder','Նշումների պանակ'),('Ближайшие напоминания','Upcoming reminders','Առաջիկա հիշեցումներ'),
 ('Очистить историю','Clear history','Մաքրել պատմությունը'),('Свернуть в трей','Minimize to tray','Նվազեցնել համակարգային վահանակ'),
 ('Распознавание','Speech recognition','Խոսքի ճանաչում'),('Микрофон','Microphone','Խոսափող'),
 ('Микрофон Windows по умолчанию','Default Windows microphone','Windows-ի լռելյայն խոսափող'),
 ('Голос озвучки','Speech voice','Արտասանության ձայն'),('Темп речи','Speech rate','Խոսքի արագություն'),
 ('Папка модели Vosk','Vosk model folder','Vosk մոդելի պանակ'),
 ('Модель / папка Whisper','Whisper model / folder','Whisper մոդել / պանակ'),
 ('Слово активации','Wake word','Ակտիվացման բառ'),
 ('Google — нужен интернет','Google — internet required','Google — անհրաժեշտ է ինտերնետ'),
 ('Vosk — без интернета, быстро','Vosk — offline, fast','Vosk — անցանց, արագ'),
 ('Добавить папку…','Add folder…','Ավելացնել պանակ…'),('Приложения (JSON)','Applications (JSON)','Ծրագրեր (JSON)'),
 ('Сохранять историю диалога на этом компьютере','Save chat history on this computer','Պահպանել զրույցների պատմությունն այս համակարգչում'),
 ('Провайдер','Provider','Մատակարար'),('Модель OpenAI','OpenAI model','OpenAI մոդել'),
 ('Модель Gemini','Gemini model','Gemini մոդել'),('Модель Groq','Groq model','Groq մոդել'),
 ('API-ключ провайдера','Provider API key','Մատակարարի API բանալի'),
 ('Удалить сохранённый ключ','Delete saved key','Ջնջել պահպանված բանալին'),
 ('Проверить выбранный ИИ','Test selected AI','Ստուգել ընտրված ԱԲ-ն'),
 ('Ключ хранится в защищённом хранилище Windows.','The key is stored in Windows protected storage.','Բանալին պահվում է Windows-ի պաշտպանված պահոցում։'),
 ('Сценарии (JSON)','Workflows (JSON)','Սցենարներ (JSON)'),('Адрес Ollama','Ollama address','Ollama հասցե'),
 ('Модель ИИ','AI model','ԱԲ մոդել'),('Доступ к публичным сайтам','Public website access','Մուտք հանրային կայքեր'),
 ('Искать актуальную информацию автоматически','Search for current information automatically','Ինքնաբերաբար փնտրել արդիական տեղեկություն'),
 ('Ollama (локально)','Ollama (local)','Ollama (տեղային)'),('Groq (быстрый)','Groq (fast)','Groq (արագ)'),
 ('Цвет фона','Background color','Ֆոնի գույն'),('Акцент','Accent','Շեշտադրում'),('Шрифт','Font','Տառատեսակ'),
 ('Размер текста','Text size','Տեքստի չափ'),('Компактный режим','Compact mode','Կոմպակտ ռեժիմ'),
 ('История хранится локально в SQLite. Разделы создаются кнопкой плюс.','History is stored locally in SQLite. Use + to create a section.','Պատմությունը պահվում է տեղային SQLite-ում։ Բաժին ստեղծելու համար սեղմեք +։'),
]
CATALOG = {lang: {r[0]:r[i] for r in ROWS} for lang,i in [('ru',0),('en',1),('hy',2)]}

class Localizer(C.QObject):
    def __init__(self, app, config):
        super().__init__(app)
        self.config = config
        app.installEventFilter(self)

    def text(self, value):
        return CATALOG.get(self.config.get('language','ru'), CATALOG['ru']).get(value, value)

    def translate_widget(self, widget):
        # Never translate editable content, chat messages, or user section names.
        if widget.objectName() == 'messageBubble' or any(p.objectName()=='messageBubble' for p in self.parents(widget)): return
        for getter,setter,key in [('windowTitle','setWindowTitle','title'),('toolTip','setToolTip','tip')]:
            value=widget.property('_source_'+key)
            if value is None:
                value=getattr(widget,getter)(); widget.setProperty('_source_'+key,value)
            if value: getattr(widget,setter)(self.text(value))
        if isinstance(widget,(W.QLabel,W.QAbstractButton)):
            value=widget.property('_source_text')
            if value is None: value=widget.text(); widget.setProperty('_source_text',value)
            widget.setText(self.text(value))
        if isinstance(widget,W.QLineEdit):
            value=widget.property('_source_placeholder')
            if value is None: value=widget.placeholderText(); widget.setProperty('_source_placeholder',value)
            widget.setPlaceholderText(self.text(value))
        if isinstance(widget,W.QTabWidget):
            for i in range(widget.count()):
                page=widget.widget(i); value=page.property('_source_tab')
                if value is None: value=widget.tabText(i); page.setProperty('_source_tab',value)
                widget.setTabText(i,self.text(value))
        if isinstance(widget,W.QComboBox):
            blocked=widget.blockSignals(True)
            for i in range(widget.count()):
                value=widget.itemData(i, C.Qt.ItemDataRole.UserRole+50)
                if value is None: value=widget.itemText(i); widget.setItemData(i,value,C.Qt.ItemDataRole.UserRole+50)
                widget.setItemText(i,self.text(value))
            widget.blockSignals(blocked)

    def parents(self, widget):
        p=widget.parentWidget()
        while p:
            yield p
            p=p.parentWidget()

    def apply(self, config):
        self.config=config
        for widget in W.QApplication.allWidgets(): self.translate_widget(widget)

    def eventFilter(self, obj, event):
        if event.type()==C.QEvent.Type.Show and isinstance(obj,W.QWidget):
            self.translate_widget(obj)
        return False

def install(app, config):
    if not hasattr(app,'friday_localizer'): app.friday_localizer=Localizer(app,config)
    app.friday_localizer.apply(config)
