"""Fallback installer for unreliable PyPI index connections.

Fetch pinned distributions using PyPI's JSON API, verify published SHA-256,
then let pip install them offline with ordinary dependency validation.
"""
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {
    "SpeechRecognition": "3.14.3", "PyAudio": "0.2.14",
    "pycaw": "20251023", "comtypes": "1.4.10", "psutil": "7.0.0",
    "vosk": "0.3.45", "srt": "3.5.3", "websockets": "15.0.1", "wheel": "0.45.1",
}


def download_chunks(url, partial, size):
    """Short range requests survive connections cut off by network proxies."""
    chunk_size = 65536
    prefix = partial.stat().st_size if partial.exists() else 0
    if prefix >= size:
        return
    segments = [(start, min(start + chunk_size, size) - 1) for start in range(prefix, size, chunk_size)]
    def fetch(segment):
        start, end = segment
        piece = partial.with_name(partial.name + f".{start}")
        if piece.exists() and piece.stat().st_size == end - start + 1:
            return piece
        for attempt in range(6):
            try:
                request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    if response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/"):
                        raise OSError("Server did not honor byte range")
                    data = response.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise OSError("Incomplete segment")
                piece.write_bytes(data)
                if start // (1024 * 1024) != (end + 1) // (1024 * 1024):
                    print(f"Progress {partial.name}: {end + 1}/{size}", flush=True)
                return piece
            except Exception as exc:
                if attempt == 0:
                    print(f"Retry range {start}: {exc}", flush=True)
                if attempt == 5:
                    raise
        raise RuntimeError("Unreachable")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        pieces = list(pool.map(fetch, segments))
    with partial.open("ab") as output:
        for piece in pieces:
            output.write(piece.read_bytes())
    for piece in pieces:
        piece.unlink()


def get_package(item):
    name, version = item
    target = ROOT / "wheelhouse"
    target.mkdir(exist_ok=True)
    metadata_path = target / f"{name}-{version}.json"
    last_error = None
    for attempt in range(8):
        try:
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            else:
                with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=45) as response:
                    metadata = json.load(response)
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            compatible = set(sys_tags())
            selected = None
            for entry in metadata["urls"]:
                if entry["filename"].endswith(".whl"):
                    if parse_wheel_filename(entry["filename"])[3] & compatible:
                        selected = entry
                        break
            if selected is None:
                selected = next(entry for entry in metadata["urls"] if entry["packagetype"] == "sdist")
            output = target / selected["filename"]
            expected = selected["digests"]["sha256"]
            if output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() == expected:
                print("Cached", name, flush=True)
                return output
            partial = output.with_suffix(output.suffix + ".part")
            download_chunks(selected["url"], partial, selected["size"])
            if partial.stat().st_size != selected["size"]:
                raise OSError(f"Incomplete download: {partial.stat().st_size}/{selected['size']} bytes")
            if hashlib.sha256(partial.read_bytes()).hexdigest() != expected:
                partial.unlink()
                raise ValueError("SHA-256 mismatch")
            os.replace(partial, output)
            print("Downloaded", name, version, flush=True)
            return output
        except Exception as exc:
            last_error = exc
            print(f"Retry {attempt + 1}/8 {name}: {exc}", flush=True)
    raise RuntimeError(f"Could not download {name}: {last_error}")


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(get_package, VERSIONS.items()))
    requirements = ROOT / "wheelhouse/bootstrap-requirements.txt"
    requirements.write_text("\n".join(f"{name}=={version}" for name, version in VERSIONS.items()) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-build-isolation", "--find-links", str(ROOT / "wheelhouse"), "-r", str(requirements)], check=True)


if __name__ == "__main__":
    main()
