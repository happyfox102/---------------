"""Integration check for metrics, the preview and playable recorded video."""
import json
from pathlib import Path
import sys
import time

from .qt import QtWidgets as W, QtCore as C
from .storage import Store
from .paths import ROOT
from .recording import RecordingPanel, M
from .pc_panel import PCPanel


def run():
    app = W.QApplication([])
    from .ui import STYLE
    app.setStyle("Fusion"); app.setStyleSheet(STYLE)
    store = Store()
    folder = ROOT / "artifacts"
    folder.mkdir(exist_ok=True)
    report = {"ok": False}
    recorder = None
    pc = None
    def pump(seconds, condition=lambda: False):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not condition():
            app.processEvents(); time.sleep(.015)
    try:
        pc = PCPanel(store)
        pc.resize(1000, 650); pc.show()
        readings = []
        pc.metrics.sample.connect(readings.append)
        pump(20, lambda: bool(readings))
        assert readings, "No PC metrics received"
        report["cpu"] = readings[-1]["cpu"]
        report["gpu"] = readings[-1]["gpu"]
        pc.grab().save(str(folder / "pc-dashboard.png"))
        pc.close_services(); pc.hide()
        recorder = RecordingPanel(store)
        recorder.resize(1000, 700); recorder.show()
        report["cameras"] = [x.description() for x in M.QMediaDevices.videoInputs()]
        for with_camera in ([False, True] if "--with-camera" in sys.argv and report["cameras"] else [False]):
            recorder.start(with_camera)
            pump(20, lambda: recorder.frames >= 45 or bool(recorder.error_text))
            assert recorder.frames >= 10, recorder.error_text or "No recorded frames"
            recorder.grab().save(str(folder / ("camera-preview.png" if with_camera else "screen-preview.png")))
            recorder.pause(False); pump(.3); recorder.pause(True); pump(.5)
            recorder.stop()
            pump(15, lambda: not recorder.active)
            assert not recorder.active and not recorder.error_text, recorder.error_text
            assert recorder.path.stat().st_size > 1000, "Empty recording"
            player = M.QMediaPlayer()
            sink = M.QVideoSink()
            player.setVideoSink(sink)
            decoded = []
            sink.videoFrameChanged.connect(lambda frame: decoded.append(frame.size()) if frame.isValid() else None)
            player.setSource(C.QUrl.fromLocalFile(str(recorder.path)))
            player.play()
            pump(10, lambda: len(decoded) >= 5)
            player.stop()
            assert len(decoded) >= 5, "Recorded MP4 cannot be decoded"
            report["camera_recording" if with_camera else "screen_recording"] = {"path": str(recorder.path), "frames": recorder.frames, "decoded": len(decoded), "width": decoded[0].width(), "height": decoded[0].height()}
        report["ok"] = True
    except Exception:
        import traceback
        report["error"] = traceback.format_exc()
    finally:
        if recorder:
            recorder.stop()
            pump(5, lambda: not recorder.active)
            recorder.close()
        if pc:
            pc.close_services(); pc.close()
    (folder / "pc-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
