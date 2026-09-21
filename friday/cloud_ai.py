"""OpenAI transport shared by chat, intent routing and the tool operator."""
import json
import time
import requests
from .credentials import openai_key, groq_key
from .web_access import Cancelled


def complete(config, messages, json_mode=False, cancel=None, on_response=None, key=None):
    is_groq = config.get('ai_provider') == 'groq'
    key = (groq_key() if is_groq else openai_key()) if key is None else key
    if not key:
        raise ValueError('Добавьте новый API-ключ: Настройки → ИИ → OpenAI.')
    model = config.get('groq_model' if is_groq else 'openai_model', 'llama-3.3-70b-versatile' if is_groq else 'gpt-4.1-mini').strip()
    if not model:
        raise ValueError('Укажите модель OpenAI в настройках.')
    payload = {'model': model, 'messages': messages, 'stream': True, 'store': False,
               'max_completion_tokens': 1200}
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
        payload['messages'] = [{'role': 'system', 'content': 'Return one valid JSON object, no markdown.'}] + messages
    if cancel is not None and cancel.is_set():
        raise Cancelled('Задача остановлена.')
    try:
        # Fixed origin: a custom Ollama URL must never receive the OpenAI key.
        endpoint = 'https://api.groq.com/openai/v1/chat/completions' if is_groq else 'https://api.openai.com/v1/chat/completions'
        session = requests.Session(); session.trust_env = False
        with session.post(endpoint,
                           headers={'Authorization': 'Bearer ' + key}, json=payload,
                           timeout=(10, 45), stream=True) as response:
            if on_response:
                on_response(response)
            if response.status_code != 200:
                label = "Groq" if is_groq else "OpenAI"
                errors = {401: 'Ключ OpenAI отклонён. Замените его в настройках.',
                          403: 'OpenAI отказал в доступе для этого аккаунта или региона.',
                          404: f'Модель {label} недоступна. Проверьте её название и доступ аккаунта.',
                          429: 'Лимит OpenAI: проверьте квоту, оплату API или повторите позже.'}
                raise ValueError(errors.get(response.status_code, f'Ошибка {label} HTTP ' + str(response.status_code)))
            output = ''; started = time.monotonic()
            for line in response.iter_lines(chunk_size=1):
                if cancel is not None and cancel.is_set():
                    raise Cancelled('Задача остановлена.')
                if time.monotonic() - started > 150:
                    raise ValueError('Истекло время ответа OpenAI.')
                if not line.startswith(b'data: '):
                    continue
                data = line[6:]
                if data == b'[DONE]':
                    break
                item = json.loads(data)
                if item.get('error'):
                    raise ValueError('OpenAI прервал ответ. Повторите запрос.')
                for choice in item.get('choices', []):
                    output += choice.get('delta', {}).get('content') or ''
                    if choice.get('finish_reason') == 'length':
                        raise ValueError('Ответ достиг лимита длины. Разделите запрос на части.')
                if len(output) > 30000:
                    raise ValueError('Ответ OpenAI слишком длинный.')
            if not output.strip():
                raise ValueError('OpenAI вернул пустой ответ.')
            return json.loads(output) if json_mode else output.strip()
    except requests.RequestException:
        raise ValueError('Нет ответа OpenAI. Проверьте интернет и доступ к API.') from None
    finally:
        if on_response:
            on_response(None)


