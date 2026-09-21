"""Start an installed local Ollama server only when it is needed."""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from .paths import ROOT


def start_local_server(url):
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1") or parsed.port not in (11434, 11435):
        return False
    root = ROOT
    portable = root / "runtime/ollama/ollama.exe"
    executable = str(portable) if portable.is_file() else shutil.which("ollama")
    if not executable:
        candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
        if not candidate.is_file():
            return False
        executable = str(candidate)
    env = os.environ.copy()
    port = parsed.port
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
    if executable == str(portable):
        env["OLLAMA_MODELS"] = str(root / "models/ollama")
    subprocess.Popen([executable, "serve"], env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.25)
    return False
