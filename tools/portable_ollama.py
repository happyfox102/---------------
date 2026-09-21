"""Extract only the CPU runtime from Ollama's official Windows release ZIP."""
import io
import os
import zipfile
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/ollama/ollama/releases/download/v0.34.0/ollama-windows-amd64.zip"


class RemoteZip(io.RawIOBase):
    def __init__(self):
        self.session = requests.Session()
        head = self.session.head(URL, allow_redirects=True, timeout=60)
        head.raise_for_status()
        total = int(head.headers["Content-Length"])
        result = self.session.get(head.url, headers={"Range": f"bytes={total - 65536}-{total - 1}"}, timeout=60)
        result.raise_for_status()
        if result.status_code != 206:
            raise RuntimeError("Server must support range requests")
        self.url = result.url
        self.size = int(result.headers["Content-Range"].split("/")[-1])
        self.tail = result.content
        self.position = 0

    def seek(self, offset, whence=0):
        self.position = offset + (self.size if whence == 2 else self.position if whence == 1 else 0)
        return self.position

    def tell(self):
        return self.position

    def read(self, size=-1):
        size = min(size if size >= 0 else self.size, self.size - self.position)
        if not size:
            return b""
        start = self.position
        if start >= self.size - len(self.tail):
            data = self.tail[start - (self.size - len(self.tail)):start - (self.size - len(self.tail)) + size]
        else:
            for attempt in range(4):
                try:
                    response = self.session.get(self.url, headers={"Range": f"bytes={start}-{start + size - 1}"}, timeout=120)
                    response.raise_for_status()
                    data = response.content
                    if response.status_code != 206 or len(data) != size:
                        raise RuntimeError("Incomplete range")
                    break
                except Exception:
                    if attempt == 3:
                        raise
        self.position += len(data)
        return data


def main():
    folder = ROOT / "runtime/ollama"
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RemoteZip()) as archive:
        files = [entry for entry in archive.infolist() if not entry.is_dir() and
                 (entry.filename == "ollama.exe" or
                  entry.filename.startswith("lib/ollama/") and
                  not any(part.startswith(("cuda", "vulkan", "rocm")) for part in Path(entry.filename).parts))]
        print("CPU runtime:", [(entry.filename, entry.compress_size) for entry in files], flush=True)
        for entry in files:
            path = (folder / entry.filename).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise RuntimeError("Unexpected ZIP path")
            if path.exists() and path.stat().st_size == entry.file_size:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".part")
            with archive.open(entry) as source, temporary.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            os.replace(temporary, path)
            print("Installed:", entry.filename, flush=True)


if __name__ == "__main__":
    main()
