"""Offline illustrated help and a tour anchored to the actual controls."""
from pathlib import Path
from .qt import QtCore as C, QtGui as G, QtWidgets as W
from .design import glyph, button, current_palette

HELP_ASSETS = Path(__file__).resolve().parents[1] / "assets/help"
CHAPTERS = [
    ("OpenAI и локальный ИИ", "ai", [
        ("1. Выберите провайдера", "Настройки → ИИ: Ollama работает на ноутбуке, OpenAI — через интернет. Укажите доступную вашему аккаунту модель и новый API-ключ. Кнопка проверки выполняет короткий платный API-запрос. Подписка ChatGPT не заменяет оплату API.", "settings_ai"),
        ("2. Сохраните ключ", "Ключ защищён Windows DPAPI и хранится в LocalAppData/FridayAssistant/secrets, отдельно от переносимой сборки. Пустое поле оставляет прежний ключ. Флажок удаления стирает сохранённый ключ. На другом компьютере его нужно ввести заново.", "settings_ai"),
        ("3. Знайте, что отправляется", "Выбранный провайдер получает вопросы, контекст диалога и результаты инструментов, которые вы запросили через агента. Автоматической отправки экрана нет. Если OpenAI недоступен, выберите Ollama. Ошибки ключа, квоты и сети показываются в ответе.", "ai")]),
    ("VPN", "globe", [
        ("1. Добавьте ключ", "Откройте VPN → Ключ / конфигурация. Введите название и полный ключ Amnezia vpn://, Happ или VLESS/VMess/Shadowsocks/Trojan/Hysteria2; также принимаются ссылки подписки HTTPS и файлы .conf/.json. Проверка определяет формат, но не доказывает работоспособность сервера.", "vpn"),
        ("2. Импортируйте в клиент", "Выберите профиль → Передать в клиент. Пятница найдёт AmneziaVPN или предложит выбрать EXE установленного клиента. Ссылка передаётся через буфер с подтверждением; файл экспортируется в выбранное место. В клиенте импортируйте и подключитесь. Для внешних клиентов состояние туннеля Пятнице неизвестно.", "vpn"),
        ("3. Подключитесь по адресу", "Сервер Windows VPN: укажите имя, IP/домен и протокол IKEv2 или SSTP от провайдера. Добавьте профиль, выберите его и нажмите Подключить. Windows запросит логин или другие данные. Статус обновляется каждые 10 секунд, пока вкладка видна. Это не AmneziaWG и не VLESS.", "vpn_server"),
        ("4. Управляйте голосом", "«Открой впн», «включи впн», «выключи впн», «статус впн». Команды действуют на выбранный профиль. Для ключей Amnezia/Happ подключение и отключение выполняются в клиенте. VPN-сервер и действующий ключ пользователь получает у провайдера.", "vpn")]),
    ("Экран и действия агента", "vision", [
        ("1. Прочитайте изображение", "Значок глаза открывает выбор PNG/JPEG. Windows OCR читает его локально и выводит текст в диалог. Используются языковые компоненты Windows; качество зависит от шрифта и размера. Постоянный захват экрана не ведётся.", "ocr"),
        ("2. Запросите действие", "«Выполни задачу …» использует включённые способности. Опасные изменения требуют «подтверждаю» в течение 60 секунд. Для мыши и клавиатуры оставляйте целевое окно активным и подтверждайте голосом. Смена окна отменяет действие. Отправка нажатия сама по себе не считается проверенным результатом.", "skills"),
        ("3. Восстановите файл", "Агент создаёт, копирует и переименовывает файлы только в папках поиска. Удаление перемещает объект в data/backups/deleted-…; рядом restore.txt с исходным путём. Вернуть его можно через Проводник. Между дисками используйте отдельное копирование с проверкой. Служебные папки защищены.", "files"),
        ("4. Способности и сценарии", "Способности и Marketplace управляют встроенными инструментами. Можно отключить ненужные. Агент выполняет не более 6 шагов, сохранённая автоматизация — до 10 допустимых шагов. После отдельного подтверждения выполняется выбранное действие; длинную задачу при необходимости задайте снова. Стоп или Esc прекращает дальнейшие шаги.", "skills")]),
    ("Интернет и браузер", "search", [
        ("1. Найдите информацию", "«Найди в интернете …» — Пятница получает результаты поиска, читает страницы и отвечает через локальную Ollama. Ссылки под ответом можно открыть нажатием. Поисковику отправляется запрос. Доступ отключается в настройках ИИ.", "ai"),
        ("2. Управляйте вкладкой", "«Браузер открой https://example.com» запускает отдельное окно Edge. «Браузер прочитай страницу» читает его текст. «Браузер найди Learn more» ищет элемент; «браузер нажми Learn more» просит подтверждение. Личные вкладки другого окна не управляются.", "windows"),
        ("3. Подключите инструменты", "В Marketplace доступны локальные Browser, Files, System и Automation. Выключенный навык недоступен агенту. «Выполни задачу покажи состояние компьютера» запускает цикл инструментов. Esc или «останови задачу» прерывает дальнейшие шаги.", "overview")]),
    ("Первые шаги", "bulb", [
        ("1. Задайте вопрос", "Введите команду в нижнее поле и нажмите стрелку. Например: «который час» или «объясни, что такое Python». Простые команды выполняются без ИИ.", "dialog"),
        ("2. Выберите раздел", "Диалог — ответы. Черновик — диктовка. Команды — примеры. Мой ПК — состояние и режимы. Значок камеры открывает студию записи.", "overview")]),
    ("Голос", "mic", [
        ("1. Одна команда", "Нажмите микрофон или Ctrl+Пробел в окне Пятницы. Дождитесь готовности и произнесите команду.", "voice"),
        ("2. Работа в фоне", "Удерживайте Ctrl и дважды нажмите Tab: микрофон включится даже в другой программе. Повторите для отключения. Кнопка «По имени» включает обращение «Пятница». Esc останавливает голос в окне программы.", "voice"),
        ("3. Выберите устройство", "Настройки → Голос: выберите микрофон и голос Windows. Vosk работает локально, Google требует интернета. Озвучка включается кнопкой в заголовке.", "settings_voice")]),
    ("Файлы и приложения", "folder", [
        ("1. Откройте программу", "«Открой мне диспетчер задач» или «открой Telegram». Программы ищутся в каталоге Windows. «Обнови список программ» обновляет каталог.", "apps"),
        ("2. Найдите папку или файл", "«Открой папку Код», «открой файл Рейтинг». При совпадениях назовите номер. Если сказать «открой папку», Пятница спросит название. Папки поиска задаются в настройках.", "files"),
        ("3. Настройте поиск", "Добавьте свои папки во вкладке «Файлы». «Обнови индекс файлов» учитывает новые файлы. Запуск исполняемых файлов требует подтверждения.", "settings_files")]),
    ("Документы и диктовка", "file", [
        ("1. Создайте документ", "«Создай Word Отчёт», «создай таблицу Бюджет», «создай txt План». Файлы сохраняются в data/documents. Внешняя таблица копируется перед изменениями.", "documents"),
        ("2. Работайте с таблицей", "«Запиши 1500 в B3», «прочитай B3», «копируй B3 в C3», «отмени изменение». Кнопка таблицы выбирает книгу. Меняется её активный лист.", "excel"),
        ("3. Диктуйте текст", "«Начни диктовку», затем текст. «Новый абзац», «удали последнее слово», «сохрани диктовку в Word». Черновик сохраняется автоматически.", "dictation")]),
    ("Заметки и напоминания", "clock", [
        ("1. Сохраните мысль", "«Запомни купить молоко», затем «покажи заметки». Заметки хранятся локально в data/notes.", "notes"),
        ("2. Поставьте таймер", "«Таймер на 5 минут», «через 20 минут напомни сделать перерыв». Для срабатывания Пятница должна оставаться запущенной, а ноутбук — не спать.", "reminders")]),
    ("Мой ПК", "pc", [
        ("1. Следите за нагрузкой", "CPU, оперативная память и наиболее загруженный движок GPU обновляются автоматически. Прочерк означает отсутствие данных драйвера. «Открой мой ПК» открывает раздел голосом.", "pc"),
        ("2. Посмотрите характеристики", "Вкладка «Характеристики» показывает процессор, видеокарту, память и Windows. Рядом отображаются питание и активность диска/сети.", "hardware"),
        ("3. Разберите хранилище", "Выберите диск и нажмите поиск. Полоса показывает ход анализа; крестик отменяет его. Категории оцениваются по путям и расширениям, недоступные данные учитываются отдельно.", "storage")]),
    ("Режимы и оптимизация", "bolt", [
        ("1. Выберите режим", "Игровой: производительность, яркость 100%, ниже фоновые приоритеты и выгрузка ИИ. Рабочий: баланс, 70%. Экономия: энергоэффективность, 40%. Можно сказать «включи игровой режим».", "modes"),
        ("2. Оптимизируйте фон", "Молния снижает приоритет подходящих фоновых приложений. Отмеченные процессы можно закрыть отдельной кнопкой после подтверждения. Документы не закрываются принудительно; рост FPS не гарантируется.", "modes"),
        ("3. Верните настройки", "Круговая стрелка восстанавливает сохранённые настройки. Отдельная выгрузка ИИ освобождает занятую моделью память; следующий ответ будет загружаться дольше.", "modes")]),
    ("Запись и скриншоты", "camera", [
        ("1. Выберите источники", "Камера в заголовке → экран, камера, разрешение и частота кадров. Начните с 720p/15 кадров/с. Микрофон добавляется флажком; системный звук не записывается.", "recording"),
        ("2. Запишите и сохраните", "Круг — экран, камера — экран с камерой в углу. Пауза временно останавливает запись, квадрат сохраняет MP4 в data/recordings. Голос: «начни запись экрана и камеры», «останови запись».", "recording"),
        ("3. Сделайте снимок", "«Сделай скриншот» сохраняет весь экран; «сделай скриншот приложения» — видимую область активного окна. PNG находятся в data/screenshots.", "screenshots")]),
    ("Windows и ИИ", "settings", [
        ("1. Управляйте ноутбуком", "«Громкость 30 процентов», «подними яркость», «яркость 50», «включи производительность». Выключение и сон требуют подтверждения. Доступность зависит от оборудования и Windows.", "windows"),
        ("2. Спросите ИИ", "Обычный вопрос отправляется выбранной модели. Некоторые сложные команды переводятся ИИ в поддерживаемое действие. «Очисти контекст ИИ» начинает новый разговор. Файлы и экран не отправляются автоматически.", "ai")]),
    ("Оформление", "palette", [
        ("1. Создайте свою тему", "Настройки → Дизайн: фон, акцент, шрифт, размер текста и плотность. Предпросмотр применяется сразу; «Сохранить» запоминает его, «Отмена» возвращает прежний.", "design"),
        ("2. Получите подсказку", "Наведите мышь на иконку, чтобы увидеть её действие. Лампочка в заголовке запускает пошаговый показ элементов. Это руководство доступно без интернета.", "overview")]),
]


class HelpPage(W.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = W.QHBoxLayout(self)
        self.menu = W.QListWidget(); self.menu.setFixedWidth(215)
        for title, name, steps in CHAPTERS:
            self.menu.addItem(W.QListWidgetItem(glyph(name), title))
        layout.addWidget(self.menu)
        self.scroll = W.QScrollArea(); self.scroll.setWidgetResizable(True); layout.addWidget(self.scroll, 1)
        self.menu.currentRowChanged.connect(self.show_chapter); self.menu.setCurrentRow(0)

    def show_chapter(self, index):
        page = W.QWidget(); layout = W.QVBoxLayout(page); layout.setSpacing(18)
        for heading, text, filename in CHAPTERS[index][2]:
            title = W.QLabel(heading); title.setObjectName("sectionTitle"); layout.addWidget(title)
            description = W.QLabel(text); description.setWordWrap(True); layout.addWidget(description)
            pix = G.QPixmap(str(HELP_ASSETS / (filename + ".png")))
            if not pix.isNull():
                shot = W.QLabel(); shot.setPixmap(pix.scaledToWidth(570, C.Qt.TransformationMode.SmoothTransformation))
                shot.setMinimumWidth(0); shot.setAlignment(C.Qt.AlignmentFlag.AlignLeft)
                shot.setToolTip("Нажмите, чтобы увеличить")
                shot.mousePressEvent = lambda event, p=pix: self.enlarge(p)
                layout.addWidget(shot)
                caption = W.QLabel("Скриншот интерфейса · учебный пример"); caption.setObjectName("muted"); layout.addWidget(caption)
        layout.addStretch()
        previous = self.scroll.takeWidget()
        if previous:
            previous.deleteLater()
        self.scroll.setWidget(page); self.scroll.verticalScrollBar().setValue(0)

    def enlarge(self, pix):
        dialog = W.QDialog(self); dialog.setWindowTitle("Пример интерфейса"); dialog.resize(1050, 780)
        layout = W.QVBoxLayout(dialog); scroll = W.QScrollArea(); label = W.QLabel(); label.setPixmap(pix)
        scroll.setWidget(label); layout.addWidget(scroll); dialog.exec()


class Tour(W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window; self.index = 0
        self.steps = [
            (lambda: window.input, "Начните с вопроса", "Напишите команду здесь. Например: «открой папку Код»."),
            (lambda: window.mic_button, "Говорите с Пятницей", "Микрофон — одна фраза. Двойное Ctrl+Tab включает постоянное прослушивание, даже в другой программе."),
            (lambda: window.tabs.tabBar(), "Всё по разделам", "Диалог, черновик, команды и состояние ПК находятся здесь."),
            (lambda: window.pc.tabs, "Ваш компьютер", "Нагрузка, характеристики, диск и режимы. Просмотр ничего не меняет."),
            (lambda: window.studio_button, "Запись экрана", "Откройте студию, выберите экран и при необходимости камеру. Запись начинается только по вашей команде."),
            (lambda: window.settings_button, "Настройте под себя", "В настройках есть голос, оформление и справка с пошаговыми скриншотами."),
            (lambda: window.guide_button, "Подсказки рядом", "Нажмите лампочку, чтобы повторить знакомство. У каждой иконки есть подсказка при наведении.")]
        self.card = W.QFrame(self); self.card.setObjectName("card"); self.card.setFixedWidth(385)
        layout = W.QVBoxLayout(self.card)
        self.count = W.QLabel(); self.count.setObjectName("muted"); layout.addWidget(self.count)
        self.heading = W.QLabel(); self.heading.setWordWrap(True); self.heading.setObjectName("sectionTitle"); layout.addWidget(self.heading)
        self.text = W.QLabel(); self.text.setWordWrap(True); layout.addWidget(self.text)
        self.progress = W.QProgressBar(); self.progress.setRange(0, len(self.steps)); self.progress.setTextVisible(False); layout.addWidget(self.progress)
        row = W.QHBoxLayout()
        close = W.QPushButton("Пропустить"); close.clicked.connect(self.close); row.addWidget(close)
        self.back = W.QPushButton("Назад"); self.back.clicked.connect(lambda: self.move_step(-1)); row.addWidget(self.back)
        self.next = W.QPushButton("Далее"); self.next.setObjectName("primary"); self.next.clicked.connect(lambda: self.move_step(1)); row.addWidget(self.next)
        layout.addLayout(row)
        self.setFocusPolicy(C.Qt.FocusPolicy.StrongFocus)
        window.installEventFilter(self)
        self.refresh(); self.show(); self.raise_(); self.setFocus()

    def move_step(self, delta):
        self.index += delta
        if self.index == len(self.steps):
            self.close(); return
        self.refresh()

    def refresh(self):
        if self.index == 3:
            self.window.tabs.setCurrentWidget(self.window.pc); self.window.pc.show_page("overview")
        elif self.index < 3:
            self.window.tabs.setCurrentWidget(self.window.dialogue)
        self.setGeometry(self.window.rect())
        self.count.setText(f"Знакомство · {self.index + 1} / {len(self.steps)}")
        self.heading.setText(self.steps[self.index][1]); self.text.setText(self.steps[self.index][2])
        self.progress.setValue(self.index + 1); self.back.setEnabled(self.index > 0)
        self.next.setText("Готово" if self.index == len(self.steps)-1 else "Далее")
        self.card.adjustSize()
        self.position(); self.update()

    def position(self):
        target = self.steps[self.index][0]()
        top = target.mapTo(self.window, C.QPoint())
        self.highlight = C.QRect(top, target.size()).adjusted(-5, -5, 5, 5)
        x = max(16, min(top.x(), self.width()-self.card.width()-16))
        y = top.y()+target.height()+18
        if y+self.card.height() > self.height()-16:
            y = max(16, top.y()-self.card.height()-18)
        self.card.move(x, y)

    def paintEvent(self, event):
        self.position()
        p = G.QPainter(self); p.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        path = G.QPainterPath(); path.addRect(C.QRectF(self.rect())); path.addRoundedRect(C.QRectF(self.highlight), 10, 10)
        p.fillPath(path, G.QColor(0, 0, 0, 175))
        p.setPen(G.QPen(G.QColor(current_palette()['accent']), 2)); p.drawRoundedRect(self.highlight, 10, 10); p.end()

    def eventFilter(self, source, event):
        if event.type() == C.QEvent.Type.Resize:
            self.setGeometry(self.window.rect()); self.position()
        return False

    def keyPressEvent(self, event):
        if event.key() == C.Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (C.Qt.Key.Key_Return, C.Qt.Key.Key_Right):
            self.move_step(1)
        elif event.key() == C.Qt.Key.Key_Left and self.index:
            self.move_step(-1)

    def closeEvent(self, event):
        self.window.tour = None
        self.window.removeEventFilter(self)
        self.window.store.config['tour_seen'] = True
        self.window.store.save_config(self.window.store.config)
        event.accept(); self.deleteLater()
