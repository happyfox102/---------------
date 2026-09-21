"""Unattended, resumable installation. Runs independently of the chat."""
import ctypes
import json
import msvcrt
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STOP = DATA / "stop-ai-install.flag"
STATUS = DATA / "ai-install-status.json"


def main():
    DATA.mkdir(exist_ok=True)
    with (DATA / "ai-install.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        with (DATA / "ai-install.log").open("a", encoding="utf-8", buffering=1) as log:
            sys.stdout = sys.stderr = log
            last_write = 0
            def report(**values):
                nonlocal last_write
                if STOP.exists():
                    raise InterruptedError("Остановлено пользователем")
                now = time.monotonic()
                if values.get("stage") == "downloading" and now - last_write < 2:
                    return
                last_write = now
                values.update(updated=datetime.now().isoformat(timespec="seconds"), pid=os.getpid())
                temporary = STATUS.with_suffix(".tmp")
                temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temporary, STATUS)
            # Only this process prevents idle system sleep. Display sleep is unchanged.
            if not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
                report(stage="error", message="Windows не разрешила предотвратить сон. Запустите установку заново.")
                return
            try:
                from connect_ai import main as connect
                attempt = 0
                while not STOP.exists():
                    attempt += 1
                    try:
                        print(f"\n{datetime.now().isoformat()} Attempt {attempt}", flush=True)
                        connect(progress=report)
                        break
                    except InterruptedError:
                        break
                    except Exception as exc:
                        traceback.print_exc()
                        report(stage="retry", message="Повторю через минуту. Скачанные части сохраняются.", error=str(exc), attempt=attempt)
                        for _ in range(60):
                            if STOP.exists():
                                break
                            time.sleep(1)
                if STOP.exists():
                    STATUS.write_text(json.dumps({"stage": "stopped", "message": "Установка остановлена. Скачанные части сохранены.", "updated": datetime.now().isoformat()}, ensure_ascii=False, indent=2), encoding="utf-8")
            finally:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    main()
