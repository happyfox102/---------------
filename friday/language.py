"""Normalize polite request wrappers without changing dictated text or filenames."""
import re


def command_phrase(text):
    text = re.sub(r"\s+", " ", str(text).replace('ё', 'е')).strip()
    # Common recognition fillers and polite Russian variants.
    text = re.sub(r"^(?:эй|слушай|пятница)[, ]+", "", text, flags=re.I)
    for _ in range(3):
        text = re.sub(r"^(?:пожалуйста[, ]+|(?:можешь|можно|могла бы ты|не могла бы ты)\s+|ты можешь\s+)", "", text, flags=re.I)
    text = re.sub(r"^(\w+),\s*пожалуйста[, ]+", r"\1 ", text, flags=re.I)
    text = re.sub(r"[, ]+пожалуйста[.! ]*$", "", text, flags=re.I)
    text = re.sub(r"^(открой|открыть|запусти|запустить|включи|включить|выключи|выключить|сделай|сделать|подними|понизь|спусти|уменьши|увеличь|установи)\s+(?:мне\s+|пожалуйста[, ]+)+", r"\1 ", text, flags=re.I)
    text = re.sub(r"^(?:открыть|открывай)\s+", "открой ", text, flags=re.I)
    text = re.sub(r"^запустить\s+", "запусти ", text, flags=re.I)
    text = re.sub(r"^сделать\s+", "сделай ", text, flags=re.I)
    text = re.sub(r"^включить\s+", "включи ", text, flags=re.I)
    text = re.sub(r"^выключить\s+", "выключи ", text, flags=re.I)
    text = re.sub(r"^(открой|запусти)\s+(?:программу|приложение)\s+", r"\1 ", text, flags=re.I)
    text = re.sub(r"^(?:открой|открывай|запусти|запускай)\s+(?:мне\s+)?", lambda m: 'открой ' if m.group(0).strip().startswith(('открой','открывай')) else 'запусти ', text, flags=re.I)
    text = re.sub(r"^(?:покажи|показывай)\s+", "покажи ", text, flags=re.I)
    text = re.sub(r"^(открой|запусти) (?:папочку|папка)\s*", r"\1 папку ", text, flags=re.I)
    text = re.sub(r"^(открой|запусти) файлик\s*", r"\1 файл ", text, flags=re.I)
    text = re.sub(r"^(открой (?:папку|файл)) (?:под названием|с названием) ", r"\1 ", text, flags=re.I)
    return text.strip()
