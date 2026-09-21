import re

WORDS = {
    "ноль": 0, "нуль": 0, "один": 1, "одна": 1, "одну": 1, "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
    "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20, "тридцать": 30,
    "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
    "восемьдесят": 80, "девяносто": 90, "сто": 100, "двести": 200,
    "триста": 300, "четыреста": 400, "пятьсот": 500, "шестьсот": 600,
    "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}


def number(text: str) -> float:
    text = text.lower().strip().replace(",", ".")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return float(text)
    sign = -1 if text.startswith("минус ") else 1
    if sign == -1:
        text = text[6:]
    words = text.split()
    if not words:
        raise ValueError("Не указано число.")
    total = group = 0
    previous = 1000
    for word in words:
        if word in ("тысяча", "тысячи", "тысяч"):
            if total:
                raise ValueError("Не удалось разобрать число.")
            total = (group or 1) * 1000
            group, previous = 0, 1000
        elif word in WORDS:
            value = WORDS[word]
            if value >= previous:
                raise ValueError("Не удалось разобрать число.")
            group += value
            previous = 100 if value >= 100 else 10 if value >= 20 else 0
        else:
            raise ValueError("Не удалось разобрать число.")
    return sign * (total + group)
