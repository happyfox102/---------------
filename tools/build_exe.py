"""Build a self-contained portable app; no user data is distributed."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build/pyinstaller-cache")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(ROOT))
from friday.qt import QApplication
from friday.ui import icon
app = QApplication([])
icon_path = ROOT / "assets/friday.ico"
icon_path.parent.mkdir(exist_ok=True)
assert icon().pixmap(64, 64).save(str(icon_path), "ICO")
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
    "--icon", str(icon_path), "--add-data", f"{ROOT / 'assets'};assets",
    "--windowed", "--name", "Пятница", "--distpath", "build/frozen", "--workpath", "build/pyinstaller",
    "--specpath", "build", "--collect-all", "vosk", "--collect-all", "speech_recognition",
    "--hidden-import", "pyaudio", "--hidden-import", "win32timezone",
    "--collect-submodules", "comtypes", "--exclude-module", "PySide6",
    "--exclude-module", "faster_whisper", "--exclude-module", "torch",
    "main.py"], check=True)
destination = ROOT / "dist/Пятница"
shutil.copytree(ROOT / "build/frozen/Пятница", destination, dirs_exist_ok=True)
# Explicitly refresh the launcher too; Windows can leave an older executable
# in a previously distributed folder while its supporting files are merged.
shutil.copy2(ROOT / "build/frozen/Пятница/Пятница.exe", destination / "Пятница.exe")
shutil.copy2(ROOT / "OPERATOR_STATUS.md", destination / "Возможности оператора.md")
def copy_changed(source, target):
    target = Path(target)
    if not target.exists() or (Path(source).stat().st_size, Path(source).stat().st_mtime_ns) != (target.stat().st_size, target.stat().st_mtime_ns):
        return shutil.copy2(source, target)
    return str(target)

for name in ("runtime/ollama", "models/ollama", "models/vosk-model-small-ru-0.22"):
    shutil.copytree(ROOT / name, destination / name, dirs_exist_ok=True,
                    copy_function=copy_changed,
                    ignore=shutil.ignore_patterns("*-partial*", "*.lock"))
(destination / "Прочитай меня.txt").write_text(
    "ПЯТНИЦА — переносимое приложение для Windows x64\n\n"
    "Запуск: Пятница.exe. Python и Ollama устанавливать не нужно.\n"
    "Переносите всю папку целиком: _internal, models и runtime необходимы.\n"
    "Сохраните папку в доступном для записи месте, например на рабочем столе.\n"
    "Настройки, история и документы сохраняются в папке data рядом с EXE.\n"
    "Ollama и Vosk работают локально. OpenAI требует интернета и API-ключа в настройках.\n"
    "VPN: Windows IKEv2/SSTP; ключи Amnezia/Happ импортируются через установленный клиент.\n"
    "Ключи защищены Windows и не включены в сборку. На другом ПК введите их заново.\n"
    "Для озвучки используется голос Windows; нужен микрофон для голосового ввода.\n"
    "Поиск в интернете и открытие сайтов требуют подключения к сети.\n"
    "Дополнительный режим Whisper в комплект не входит; выбран локальный Vosk.\n",
    encoding="utf-8-sig")
print(destination / "Пятница.exe", flush=True)
