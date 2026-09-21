"""Exercise profiles and priority changes, restoring all original settings."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from friday.pc_services import Optimizer
from friday.storage import Store
from friday.system_actions import brightness, configured_modes

before = (brightness(), configured_modes())
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], creationflags=subprocess.CREATE_NO_WINDOW)
report = {}
try:
    with tempfile.TemporaryDirectory() as temp:
        optimizer = Optimizer(Store(Path(temp)))
        proc = psutil.Process(child.pid)
        priority = proc.nice()
        lower = optimizer.lower
        with patch('friday.pc_services.BACKGROUND', {'python.exe'}), patch.object(optimizer, 'lower', side_effect=lambda selected=None: lower({child.pid})):
            try:
                for mode in ('game', 'work', 'save'):
                    report[mode] = optimizer.profile(mode)
                    report[mode + '_brightness'] = brightness()
                assert proc.nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS
            finally:
                report['restore'] = optimizer.restore()
        assert proc.nice() == priority
        assert (brightness(), configured_modes()) == before
        report['ok'] = True
finally:
    child.terminate(); child.wait(10)
(ROOT / 'artifacts/profiles-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
