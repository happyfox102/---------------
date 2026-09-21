"""Windows VPN profiles and encrypted imports for installed VPN clients."""
import configparser
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
import uuid
from .credentials import Secrets


def classify(value):
    value = value.strip()
    if not value or len(value) > 262144 or '\x00' in value:
        raise ValueError('Пустой или слишком большой ключ (максимум 256 КБ).')
    scheme = urlsplit(value).scheme.lower() if '://' in value[:20] else ''
    if scheme in {'vpn', 'vless', 'vmess', 'trojan', 'ss', 'socks', 'socks5', 'hy2', 'hysteria2', 'happ', 'https'}:
        if any(c.isspace() for c in value) or not value.split('://', 1)[1]:
            raise ValueError('Вставьте одну полную ссылку без пробелов.')
        if scheme == 'happ' and not value.startswith(('happ://crypto', 'happ://add/')):
            raise ValueError('Поддерживается импорт happ://crypto… или happ://add/…')
        if scheme == 'https' and (not urlsplit(value).hostname or urlsplit(value).username):
            raise ValueError('Некорректная ссылка подписки.')
        return {'format': scheme.upper(), 'client': 'AmneziaVPN' if scheme == 'vpn' else 'Happ', 'file': False}
    if value.startswith('[Interface]'):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try: parser.read_string(value)
        except configparser.Error: raise ValueError('Некорректный файл конфигурации.') from None
        if not parser.has_option('Interface', 'PrivateKey') or not parser.has_option('Peer', 'PublicKey'):
            raise ValueError('В конфигурации отсутствуют ключи Interface/Peer.')
        awg = any(k.lower() in parser['Interface'] for k in ('Jc', 'S1', 'S2', 'H1'))
        return {'format': 'AmneziaWG' if awg else 'WireGuard', 'client': 'AmneziaVPN', 'file': True}
    if value.startswith(('{', '[')):
        try: data = json.loads(value)
        except ValueError: raise ValueError('Некорректный JSON.') from None
        if not isinstance(data, (dict, list)) or not data:
            raise ValueError('Пустая конфигурация JSON.')
        return {'format': 'JSON', 'client': 'AmneziaVPN' if isinstance(data, dict) and 'containers' in data else 'Happ', 'file': True}
    raise ValueError('Формат не распознан. Для IP используйте «Сервер Windows VPN»; для Amnezia/Happ вставьте полный ключ или импортируйте .conf/.json.')


def server_address(value):
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if len(value) > 253 or not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', value):
        raise ValueError('Введите IP или домен сервера, без протокола и порта.')
    if any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-') for part in value.split('.')):
        raise ValueError('Некорректное имя сервера.')
    return value


class VPN:
    def __init__(self, store, secrets=None):
        self.store = store
        self.secrets = secrets if secrets is not None else Secrets()

    def profiles(self):
        return self.store.read('vpn.json', [])

    def import_key(self, name, value):
        info = classify(value)
        name = name.strip()
        if not name or len(name) > 60: raise ValueError('Название профиля: от 1 до 60 символов.')
        profile = {'id': uuid.uuid4().hex, 'name': name, 'kind': 'external', **info}
        self.secrets.set('vpn-' + profile['id'], value.strip())
        try: self.store.write('vpn.json', self.profiles() + [profile])
        except Exception:
            self.secrets.delete('vpn-' + profile['id']); raise
        return profile

    def remove(self, profile):
        if profile['kind'] == 'windows':
            self._ps('remove', {'name': profile['entry']})
        self.store.write('vpn.json', [p for p in self.profiles() if p['id'] != profile['id']])
        self.secrets.delete('vpn-' + profile['id'])

    @staticmethod
    def _ps(action, data=None):
        scripts = {
            'list': '@(Get-VpnConnection | Select-Object Name,ConnectionStatus) | ConvertTo-Json -Compress',
            'add': 'Add-VpnConnection -Name $v.name -ServerAddress $v.server -TunnelType $v.protocol -EncryptionLevel Required -RememberCredential -Force | Out-Null',
            'remove': 'Remove-VpnConnection -Name $v.name -Force -ErrorAction Stop',
        }
        prefix = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $v=[Console]::In.ReadToEnd() | ConvertFrom-Json; "
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', prefix + scripts[action]],
                                input=json.dumps(data or {}), capture_output=True, text=True, encoding='utf-8',
                                timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise ValueError('Windows не выполнила операцию VPN. Проверьте права и настройки сетевой службы.')
        return json.loads(result.stdout.lstrip('\ufeff') or '[]') if action == 'list' else None

    def add_server(self, name, address, protocol):
        address = server_address(address)
        if not re.fullmatch(r'[\w .-]{1,60}', name.strip()) or protocol not in ('Ikev2', 'Sstp'):
            raise ValueError('Проверьте название и протокол VPN.')
        ident = uuid.uuid4().hex
        entry = 'Friday-' + ident[:8] + ' ' + name.strip()
        self._ps('add', {'name': entry, 'server': address, 'protocol': protocol})
        profile = {'id': ident, 'name': name.strip(), 'kind': 'windows', 'entry': entry, 'format': protocol, 'server': address}
        try: self.store.write('vpn.json', self.profiles() + [profile])
        except Exception:
            self._ps('remove', {'name': entry}); raise
        return profile

    def statuses(self):
        values = self._ps('list')
        if isinstance(values, dict): values = [values]
        return {v['Name']: v['ConnectionStatus'] for v in (values or [])}

    def connect(self, profile):
        if profile['kind'] != 'windows': raise ValueError('Подключение этим ключом выполняется в VPN-клиенте.')
        subprocess.Popen(['rasphone.exe', '-d', profile['entry']])
        return 'Открыто подключение Windows. Введите данные провайдера. Статус обновится после подключения.'

    def disconnect(self, profile):
        if profile['kind'] != 'windows': raise ValueError('Отключите туннель в приложении VPN-клиента.')
        result = subprocess.run(['rasdial.exe', profile['entry'], '/disconnect'], capture_output=True,
                                timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise ValueError('Не удалось отключить VPN. Проверьте состояние в Windows.')
        return 'Запрос отключения передан Windows.'

    def client_path(self, profile):
        configured = self.store.config.get('vpn_clients', {}).get(profile['client'])
        candidates = [Path(configured)] if configured else []
        for root in (os.environ.get('ProgramFiles', ''), os.environ.get('ProgramFiles(x86)', ''), os.environ.get('LOCALAPPDATA', '')):
            for relative in ('AmneziaVPN/AmneziaVPN.exe',) if profile['client'] == 'AmneziaVPN' else ('Happ/Happ.exe', 'FlyFrogLLC/Happ/Happ.exe', 'Programs/Happ/Happ.exe', 'Happ/happ.exe'):
                candidates.append(Path(root) / relative)
        return next((p for p in candidates if p.is_file() and p.suffix.lower() == '.exe'), None)

    def open_client(self, profile):
        path = self.client_path(profile)
        if not path: raise ValueError('Клиент ' + profile['client'] + ' не найден. Укажите его EXE кнопкой «Выбрать клиент».')
        subprocess.Popen([str(path)], cwd=str(path.parent))
