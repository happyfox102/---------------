"""Google Gemini REST transport with the same interface as the local/cloud providers."""
import json
import time
import requests
from .credentials import Secrets
from .web_access import Cancelled


def key():
    return Secrets().get('gemini') or ''


def complete(config, messages, json_mode=False, cancel=None):
    api_key = key()
    if not api_key:
        raise ValueError('Добавьте ключ Gemini в Настройки → ИИ.')
    model = config.get('gemini_model', 'gemini-flash-latest').strip()
    parts = []
    for message in messages:
        role = 'user' if message.get('role') != 'assistant' else 'model'
        parts.append({'role': role, 'parts': [{'text': str(message.get('content', ''))}]})
    if json_mode:
        parts.insert(0, {'role': 'user', 'parts': [{'text': 'Верни только один JSON-объект без markdown.'}]})
    try:
        session = requests.Session(); session.trust_env = False
        payload = {'contents': parts, 'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 1200,
                  **({'responseMimeType': 'application/json'} if json_mode else {})}}
        for attempt in range(3):
            response = session.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'Content-Type': 'application/json', 'x-goog-api-key': api_key},
                json=payload, timeout=(10, 60))
            if response.status_code != 503 or attempt == 2:
                break
            time.sleep(1.5 * (attempt + 1))
    except requests.RequestException:
        raise ValueError('Нет соединения с Gemini. Проверьте интернет, прокси или выберите Ollama.') from None
    if cancel and cancel.is_set(): raise Cancelled('Задача остановлена.')
    if response.status_code != 200:
        if response.status_code == 400 and 'location' in response.text.lower():
            raise ValueError('Gemini API недоступен в регионе, который определил Google. Выберите Ollama или другой поддерживаемый провайдер.')
        messages = {400: 'Gemini отклонил запрос или модель недоступна.', 401: 'Ключ Gemini недействителен.',
                    403: 'У ключа Gemini нет доступа к API.', 429: 'Лимит Gemini исчерпан; выберите Ollama или повторите позже.'}
        raise ValueError(messages.get(response.status_code, 'Ошибка Gemini HTTP ' + str(response.status_code)))
    try:
        text = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except (ValueError, KeyError, IndexError, TypeError):
        raise ValueError('Gemini вернул пустой или неподдерживаемый ответ.') from None
    return json.loads(text) if json_mode else text
