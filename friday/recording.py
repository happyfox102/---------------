"""Screen/camera composition and MP4 recording using bundled Qt Multimedia."""
import os
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
import shutil
import time
from datetime import datetime

from .qt import QtCore as C, QtGui as G, QtWidgets as W, Signal
from .design import button as style_button, LoadingBar
try:
    from PySide6 import QtMultimedia as M
except ImportError:
    from PyQt6 import QtMultimedia as M


def composite(screen, camera, size, corner=0):
    image = G.QImage(size, G.QImage.Format.Format_RGB32)
    image.fill(G.QColor("#0c111b"))
    painter = G.QPainter(image)
    painter.setRenderHint(G.QPainter.RenderHint.SmoothPixmapTransform)
    if not screen.isNull():
        scaled = screen.scaled(size, C.Qt.AspectRatioMode.KeepAspectRatio, C.Qt.TransformationMode.SmoothTransformation)
        painter.drawImage((size.width() - scaled.width()) // 2, (size.height() - scaled.height()) // 2, scaled)
    if not camera.isNull():
        width = size.width() // 4
        height = width * camera.height() // max(1, camera.width())
        x = size.width() - width - 16 if corner == 0 else 16
        y = size.height() - height - 16
        painter.setPen(G.QPen(G.QColor("#73dfc1"), 3))
        painter.drawRect(x - 2, y - 2, width + 4, height + 4)
        painter.drawImage(C.QRect(x, y, width, height), camera)
    painter.end()
    return image


class RecordingPanel(W.QWidget):
    message = Signal(str)
    activeChanged = Signal(bool)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.active = False
        self.stopping = False
        self.latest_camera = G.QImage()
        self.frames = 0
        self.dropped = 0
        self.camera = None
        self.path = None
        self.elapsed = 0.0
        self.last_frame = 0.0
        self.error_text = ""
        self.session = M.QMediaCaptureSession(self)
        self.video = M.QVideoFrameInput(self)
        self.recorder = M.QMediaRecorder(self)
        self.session.setVideoFrameInput(self.video)
        self.session.setRecorder(self.recorder)
        self.recorder.recorderStateChanged.connect(self.state_changed)
        self.recorder.errorOccurred.connect(lambda error, text: self.fail(text))
        self.camera_session = M.QMediaCaptureSession(self)
        self.sink = M.QVideoSink(self)
        self.camera_session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self.camera_frame)
        self.timer = C.QTimer(self)
        self.timer.timeout.connect(self.capture)
        layout = W.QVBoxLayout(self)
        title = W.QLabel("Запись"); title.setObjectName("sectionTitle"); layout.addWidget(title)
        row = W.QHBoxLayout()
        self.screen_choice = W.QComboBox()
        for index, screen in enumerate(G.QGuiApplication.screens()):
            self.screen_choice.addItem(f"Экран {index + 1} · {screen.size().width()}×{screen.size().height()}", screen)
        row.addWidget(self.screen_choice)
        self.camera_choice = W.QComboBox()
        self.devices = M.QMediaDevices(self)
        self.devices.videoInputsChanged.connect(self.refresh_cameras)
        self.refresh_cameras()
        row.addWidget(self.camera_choice)
        self.resolution = W.QComboBox()
        self.resolution.addItems(["720p · меньше нагрузка", "1080p"])
        row.addWidget(self.resolution)
        self.fps = W.QComboBox()
        self.fps.addItems(["15 кадров/с", "30 кадров/с"])
        row.addWidget(self.fps)
        layout.addLayout(row)
        row = W.QHBoxLayout()
        self.mic = W.QCheckBox("Микрофон")
        self.mic.setToolTip("Записывать микрофон. Системный звук не записывается.")
        row.addWidget(self.mic)
        self.audio_choice = W.QComboBox()
        for device in M.QMediaDevices.audioInputs():
            self.audio_choice.addItem(device.description(), device)
        row.addWidget(self.audio_choice)
        self.corner = W.QComboBox()
        self.corner.addItems(["Камера справа", "Камера слева"])
        row.addWidget(self.corner)
        layout.addLayout(row)
        self.preview = W.QLabel("Предпросмотр появится после запуска записи")
        self.preview.setAlignment(C.Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(200)
        self.preview.setObjectName("detailCard")
        layout.addWidget(self.preview, 1)
        self.status = W.QLabel("Готово к записи")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = LoadingBar(); layout.addWidget(self.progress)
        row = W.QHBoxLayout()
        self.start_button = W.QPushButton("● Записать экран")
        self.start_button.clicked.connect(lambda: self.start(False))
        self.both_button = W.QPushButton("● Экран + камера")
        self.both_button.clicked.connect(lambda: self.start(True))
        self.pause_button = W.QPushButton("Пауза / продолжить")
        self.pause_button.clicked.connect(lambda: self.pause())
        self.stop_button = W.QPushButton("■ Сохранить запись")
        self.stop_button.clicked.connect(self.stop)
        for button in (self.start_button, self.both_button, self.pause_button, self.stop_button):
            row.addWidget(button)
        layout.addLayout(row)
        folder = W.QPushButton("Открыть папку записей")
        folder.clicked.connect(self.open_folder)
        layout.addWidget(folder)
        for control, name, label in ((self.start_button,'record','Экран'),(self.both_button,'camera','Экран + камера'),(self.pause_button,'pause','Пауза'),(self.stop_button,'stop','Сохранить'),(folder,'folder','Мои записи')):
            style_button(control, name, label)
        self.pause_button.setEnabled(False); self.stop_button.setEnabled(False)

    def refresh_cameras(self):
        if self.active:
            return
        self.camera_choice.clear()
        for device in M.QMediaDevices.videoInputs():
            self.camera_choice.addItem(device.description(), device)
        if not self.camera_choice.count():
            self.camera_choice.addItem("Камера не обнаружена", None)

    def open_folder(self):
        folder = self.store.data / "recordings"
        folder.mkdir(exist_ok=True)
        os.startfile(folder)

    def start(self, with_camera=False):
        if self.active:
            self.message.emit("Запись уже идёт.")
            return
        if with_camera and self.camera_choice.currentData() is None:
            self.message.emit("Камера не найдена. Подключите её и проверьте разрешения Windows.")
            return
        if self.mic.isChecked() and self.audio_choice.currentData() is None:
            self.message.emit("Микрофон для записи не найден.")
            return
        if self.screen_choice.currentData() not in G.QGuiApplication.screens():
            self.message.emit("Выбранный экран отключён. Перезапустите приложение для обновления списка.")
            return
        folder = self.store.data / "recordings"
        folder.mkdir(exist_ok=True)
        if shutil.disk_usage(folder).free < 512 * 1024**2:
            self.message.emit("Для записи нужно не менее 512 МБ свободного места.")
            return
        self.path = self.store.unique_path("recordings", datetime.now().strftime("%Y-%m-%d %H-%M-%S"), ".mp4")
        self.size = C.QSize(1280, 720) if self.resolution.currentIndex() == 0 else C.QSize(1920, 1080)
        self.rate = 15 if self.fps.currentIndex() == 0 else 30
        self.with_camera = with_camera
        self.frames = self.dropped = 0
        self.error_text = ""
        self.elapsed = 0
        self.started = self.last_frame = time.monotonic()
        self.latest_camera = G.QImage()
        media_format = M.QMediaFormat(M.QMediaFormat.FileFormat.MPEG4)
        media_format.setVideoCodec(M.QMediaFormat.VideoCodec.H264)
        media_format.setAudioCodec(M.QMediaFormat.AudioCodec.AAC)
        self.recorder.setMediaFormat(media_format)
        self.recorder.setVideoResolution(self.size)
        self.recorder.setVideoFrameRate(self.rate)
        self.recorder.setQuality(M.QMediaRecorder.Quality.NormalQuality)
        self.recorder.setOutputLocation(C.QUrl.fromLocalFile(str(self.path)))
        self.audio = M.QAudioInput(self.audio_choice.currentData(), self) if self.mic.isChecked() else None
        self.session.setAudioInput(self.audio)
        if with_camera:
            self.camera = M.QCamera(self.camera_choice.currentData(), self)
            self.camera.errorOccurred.connect(lambda error, text: self.fail("Камера: " + text))
            self.camera_session.setCamera(self.camera)
            self.camera.start()
        self.active, self.stopping = True, False
        for control in self.controls():
            control.setEnabled(False)
        self.activeChanged.emit(True)
        self.pause_button.setEnabled(True); self.stop_button.setEnabled(True)
        self.progress.loading(True, "Подключаю источники записи")
        self.status.setText("Подключение источников записи…")
        self.recorder.record()
        if self.active:
            self.timer.start(round(1000 / self.rate))

    def controls(self):
        return (self.start_button, self.both_button, self.screen_choice, self.camera_choice, self.resolution, self.fps, self.mic, self.audio_choice)

    def camera_frame(self, frame):
        if self.active:
            self.latest_camera = frame.toImage()

    def capture(self):
        if not self.active or self.stopping or self.recorder.recorderState() == M.QMediaRecorder.RecorderState.PausedState:
            self.last_frame = time.monotonic()
            return
        now = time.monotonic()
        if self.with_camera and self.latest_camera.isNull():
            if now - self.started > 10:
                self.fail("Камера не передаёт изображение. Проверьте доступ к камере в Windows.")
            return
        screen = self.screen_choice.currentData()
        if screen not in G.QGuiApplication.screens():
            self.fail("Экран отключён.")
            return
        picture = screen.grabWindow(0).toImage()
        if picture.isNull():
            self.fail("Windows не разрешила захват экрана.")
            return
        image = composite(picture, self.latest_camera, self.size, self.corner.currentIndex())
        if self.frames:
            self.elapsed += now - self.last_frame
        self.last_frame = now
        frame = M.QVideoFrame(image)
        frame.setStartTime(int(self.elapsed * 1_000_000))
        frame.setEndTime(int((self.elapsed + 1 / self.rate) * 1_000_000))
        if self.video.sendVideoFrame(frame):
            self.frames += 1
        else:
            self.dropped += 1
        if self.frames == 1:
            self.progress.loading(False)
            self.message.emit("Запись экрана" + (" и камеры" if self.with_camera else "") + " включена.")
        if self.isVisible():
            self.preview.setPixmap(G.QPixmap.fromImage(image).scaled(self.preview.size(), C.Qt.AspectRatioMode.KeepAspectRatio, C.Qt.TransformationMode.SmoothTransformation))
        self.status.setText(f"● REC  {int(self.elapsed)//60:02}:{int(self.elapsed)%60:02}  ·  {self.frames/max(1,self.elapsed):.1f} кадр/с  ·  кадров {self.frames}  ·  пропущено {self.dropped}\n{self.path}")
        if now - self.started > 8 and not self.frames:
            self.fail("Видеокодек не принимает кадры.")
        if self.frames % (self.rate * 5) == 0 and shutil.disk_usage(self.path.parent).free < 256 * 1024**2:
            self.message.emit("Место на диске заканчивается. Сохраняю запись.")
            self.stop()

    def pause(self, resume=None):
        if self.active and not self.stopping:
            paused = self.recorder.recorderState() == M.QMediaRecorder.RecorderState.PausedState
            if resume is not None and resume != paused:
                return
            if paused:
                self.pause_button.setText("Пауза")
                self.last_frame = time.monotonic()
                self.recorder.record()
            else:
                self.pause_button.setText("Продолжить")
                self.recorder.pause()
                self.status.setText("Ⅱ Запись на паузе")

    def stop(self):
        if not self.active or self.stopping:
            return
        self.stopping = True
        self.timer.stop()
        if self.camera:
            self.camera.stop()
        self.status.setText("Сохраняю MP4…")
        self.progress.loading(True, "Сохраняю видео")
        self.recorder.stop()
        if self.recorder.recorderState() == M.QMediaRecorder.RecorderState.StoppedState:
            self.finish()

    def state_changed(self, state):
        if state == M.QMediaRecorder.RecorderState.StoppedState and self.active:
            self.finish()

    def fail(self, text):
        self.error_text = text
        self.message.emit("Ошибка записи: " + text)
        self.stop()
        if not self.active:
            self.progress.loading(False)
            self.status.setText("Ошибка записи: " + text)

    def finish(self):
        if not self.active:
            return
        self.active = False
        self.progress.loading(False)
        self.pause_button.setEnabled(False); self.stop_button.setEnabled(False)
        self.pause_button.setText("Пауза")
        self.timer.stop()
        if self.camera:
            self.camera.stop()
            self.camera_session.setCamera(None)
            self.camera.deleteLater()
            self.camera = None
        self.session.setAudioInput(None)
        if self.audio:
            self.audio.deleteLater()
            self.audio = None
        for control in self.controls():
            control.setEnabled(True)
        self.activeChanged.emit(False)
        text = "Ошибка записи: " + self.error_text if self.error_text else f"Запись сохранена: {self.path}" if self.frames and self.path.is_file() else "Запись завершена без кадров."
        self.status.setText(text)
        self.message.emit(text)
