"""Copy compatible, already installed Python 3.12 distributions into the local venv.

No global packages are modified; this avoids redownloading Qt on this machine.
Only site-packages files listed by installed distribution metadata are copied.
"""
import importlib.metadata
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["PyQt6", "PyQt6-Qt6", "PyQt6-sip", "openpyxl", "et_xmlfile", "python-docx", "lxml",
         "requests", "urllib3", "charset-normalizer", "idna", "certifi", "typing_extensions",
         "pywin32", "cffi", "pycparser", "colorama", "tqdm", "setuptools", "packaging"]


def main():
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Run using the installed global Python 3.12, not another Python version")
    target = ROOT / ".venv/Lib/site-packages"
    if not target.is_dir():
        raise RuntimeError("Create .venv first")
    for name in NAMES:
        dist = importlib.metadata.distribution(name)
        canonical = name.lower().replace("_", "-")
        if any(d.metadata["Name"].lower().replace("_", "-") == canonical for d in importlib.metadata.distributions(path=[str(target)])):
            print(f"Already present: {name}", flush=True)
            continue
        source = Path(dist.locate_file("")).resolve()
        count = 0
        for entry in dist.files or []:
            path = Path(dist.locate_file(entry)).resolve()
            if not path.is_relative_to(source) or not path.is_file():
                continue
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            count += 1
        print(f"Copied {name} {dist.version}: {count} files", flush=True)


if __name__ == "__main__":
    main()
