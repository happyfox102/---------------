"""Download the official Russian Vosk model, without running model-supplied code."""
import os
import sys
import urllib.request
import zipfile
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "vosk-model-small-ru-0.22"
URL = f"https://alphacephei.com/vosk/models/{NAME}.zip"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror", action="store_true", help="Use the pinned Rhasspy mirror on Hugging Face if the official host is unavailable")
    args = parser.parse_args()
    folder = ROOT / "models"
    folder.mkdir(exist_ok=True)
    target = folder / NAME
    if (target / "am/final.mdl").is_file() and (target / "conf/model.conf").is_file():
        print("Model is already installed:", target)
        return
    archive = folder / (NAME + ".zip")
    partial = archive.with_suffix(".part")
    url = "https://huggingface.co/rhasspy/vosk-models/resolve/e7ac2109d134b5f2404ba95389b2fb51916d4cab/ru/vosk-model-small-ru-0.22.zip" if args.mirror else URL
    print("Downloading Vosk model (~45 MB):", url, flush=True)
    for attempt in range(5):
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                append = offset > 0 and response.status == 206
                total = offset if append else 0
                expected = total + int(response.headers.get("Content-Length", "0"))
                last_mb = -1
                with partial.open("ab" if append else "wb") as output:
                    while chunk := response.read(65536):
                        output.write(chunk)
                        total += len(chunk)
                        current_mb = total // (1024 * 1024)
                        if current_mb != last_mb:
                            print(f"{current_mb} MB", flush=True)
                            last_mb = current_mb
                if expected and total != expected:
                    raise OSError("Incomplete download")
            break
        except Exception as exc:
            if attempt == 4:
                raise
            print(f"Download interrupted ({exc}); resuming, attempt {attempt + 2}/5", flush=True)
    os.replace(partial, archive)
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            destination = (folder / entry.filename).resolve()
            if not destination.is_relative_to(folder.resolve()) or not entry.filename.startswith(NAME + "/"):
                raise ValueError("Unexpected archive path")
        if z.testzip():
            raise ValueError("Archive is corrupted")
        z.extractall(folder)
    print("Installed:", target)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Download failed:", exc, file=sys.stderr)
        sys.exit(1)
