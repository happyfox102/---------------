"""Hardware integration check; restore original brightness and active power plan."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from friday.storage import Store
from friday.apps import AppCatalog
from friday.system_actions import brightness, active_plan, powercfg, power_mode, screenshot, configured_modes
from friday.qt import QApplication, QtGui

app = QApplication([])
report = {}
catalog = AppCatalog(Store())
catalog.refresh(force=True)
catalog.thread.join(30)
report["programs"] = len(catalog.entries)
report["catalog_error"] = catalog.error
assert catalog.entries, catalog.error
before = brightness()
try:
    report["brightness_set"] = brightness(value=max(1, before - 1))
    report["brightness_read"] = brightness()
finally:
    brightness(value=before)
report["brightness_restored"] = brightness()
plan = active_plan()
original_modes = configured_modes()
try:
    report["saver"] = power_mode("saver")
    report["performance"] = power_mode("performance")
finally:
    configured_modes(original_modes)
    assert powercfg("/setactive", plan).returncode == 0
assert active_plan() == plan
report["power_restored"] = True
folder = ROOT / "artifacts"
folder.mkdir(exist_ok=True)
for active in (False, True):
    path = folder / ("active-window-check.png" if active else "screen-check.png")
    screenshot(path, active)
    image = QtGui.QImage(str(path))
    assert not image.isNull()
    report[path.stem] = [image.width(), image.height()]
(folder / "windows-features.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
