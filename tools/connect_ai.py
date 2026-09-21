"""Download and connect the local model after Ollama is installed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from friday.ai import start_local_server
from friday.engine import Engine
from friday.storage import Store

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
URL = "http://127.0.0.1:11435"


def main(progress=None):
    report = progress or (lambda **kwargs: None)
    report(stage="starting", message="Запускаю Ollama")
    try:
        requests.get(URL + "/api/version", timeout=3).raise_for_status()
    except requests.RequestException:
        if not start_local_server(URL):
            raise RuntimeError("Ollama is not installed or could not start")
    previous = None
    with requests.post(URL + "/api/pull", json={"model": MODEL, "stream": True}, stream=True, timeout=(5, 180)) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            item = json.loads(line)
            if item.get("error"):
                raise RuntimeError(item["error"])
            report(stage="downloading", message=item.get("status", "Загрузка"),
                   completed=item.get("completed", 0), total=item.get("total", 0))
            percent = int(item.get("completed", 0) / max(item.get("total", 1), 1) * 10) * 10
            status = (item.get("status"), percent)
            if status != previous:
                print(status[0], str(percent) + "%" if item.get("total") else "", flush=True)
                previous = status
    report(stage="checking", message="Модель скачана. Проверяю ответы и перевод")
    store = Store()
    config = store.config.copy()
    config.update(ollama_url=URL, ollama_model=MODEL)
    store.config = config
    engine = Engine(store)
    answer = engine.ask_ai("Ответь одним словом: столица Франции?")
    print("Test:", answer, flush=True)
    if "париж" not in answer.casefold():
        raise RuntimeError("AI response check failed; settings were not changed")
    translation = engine.ask_ai("Переведи на английский только фразу: добрый вечер")
    print("Translation:", translation, flush=True)
    if "good evening" not in translation.casefold():
        raise RuntimeError("Translation check failed; settings were not changed")
    # Preserve settings the user may have changed during the long check.
    latest = Store()
    config = latest.config.copy()
    config.update(ollama_url=URL, ollama_model=MODEL)
    latest.save_config(config)
    print("Connected successfully:", MODEL, flush=True)
    report(stage="complete", message="ИИ установлен и подключён. Перезапустите Пятницу.")


if __name__ == "__main__":
    main()
