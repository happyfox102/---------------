import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from friday.cloud_ai import complete
from friday.credentials import Secrets
from friday.vpn import VPN, classify, server_address
from friday.storage import Store
from friday.engine import Engine
from friday.web_access import Cancelled


class CloudTests(unittest.TestCase):
    def response(self, text):
        response = Mock(status_code=200)
        response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.iter_lines.return_value = [b'data: ' + json.dumps({'choices': [{'delta': {'content': text}}]}).encode(), b'data: [DONE]']
        return response

    def test_stream_and_fixed_origin(self):
        with patch('friday.cloud_ai.requests.post', return_value=self.response('Готово')) as post:
            result = complete({'ollama_url': 'http://evil.invalid'}, [{'role': 'user', 'content': 'Тест'}], key='test-only')
        self.assertEqual(result, 'Готово')
        self.assertEqual(post.call_args.args[0], 'https://api.openai.com/v1/chat/completions')
        self.assertFalse(post.call_args.kwargs['json']['store'])

    def test_json_and_error_do_not_echo_server_body(self):
        with patch('friday.cloud_ai.requests.post', return_value=self.response('{"action":"unknown"}')):
            self.assertEqual(complete({}, [], True, key='test-only'), {'action': 'unknown'})
        response = self.response('secret'); response.status_code = 401
        with patch('friday.cloud_ai.requests.post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'отклонён'): complete({}, [], key='test-only')
        response.json.assert_not_called()

    def test_cancel_and_missing_key_never_call_network(self):
        with patch('friday.cloud_ai.requests.post') as post:
            with self.assertRaises(ValueError): complete({}, [], key='')
            event = threading.Event(); event.set()
            with self.assertRaises(Cancelled): complete({}, [], cancel=event, key='test-only')
        post.assert_not_called()

    def test_chat_and_operator_use_cloud_with_no_ollama_model(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)); store.config.update(ai_provider='openai', ollama_model='', web_auto=False)
            engine = Engine(store, Mock())
            with patch('friday.cloud_ai.complete', return_value='Ответ') as request:
                self.assertEqual(engine.ask_ai('Привет'), 'Ответ')
                self.assertEqual(engine.operator._model([]), 'Ответ')
                self.assertEqual(request.call_count, 2)

    def test_dpapi_roundtrip_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            secrets = Secrets(Path(temp)); secrets.set('test', 'учебный-секрет')
            self.assertEqual(secrets.get('test'), 'учебный-секрет')
            self.assertNotIn('учебный-секрет'.encode(), (Path(temp)/'test.bin').read_bytes())
            secrets.delete('test'); self.assertEqual(secrets.get('test'), '')


class VPNTests(unittest.TestCase):
    def test_supported_families(self):
        for key, client in [('vpn://example', 'AmneziaVPN'), ('vless://id@example.com:443', 'Happ'), ('happ://crypto/example', 'Happ'), ('https://example.com/subscription', 'Happ')]:
            self.assertEqual(classify(key)['client'], client)
        self.assertEqual(classify('[Interface]\nPrivateKey=test\nJc=4\n[Peer]\nPublicKey=test')['format'], 'AmneziaWG')

    def test_no_arbitrary_schemes_or_shell_addresses(self):
        for value in ('file:///C:/x', 'powershell://x', 'happ://run/command', 'vpn://', 'vless://a b', '127.0.0.1'):
            with self.assertRaises(ValueError): classify(value)
        for value in ('host;whoami', 'https://example.com', 'bad..host', '-bad.example', 'host:443'):
            with self.assertRaises(ValueError): server_address(value)
        self.assertEqual(server_address('2001:db8::1'), '2001:db8::1')

    def test_import_never_saves_key_in_metadata_and_removes_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)); secrets = Secrets(Path(temp)/'private')
            service = VPN(store, secrets); key = 'vpn://test-only-secret'
            profile = service.import_key('Тест', key)
            self.assertNotIn(key, (store.data/'vpn.json').read_text(encoding='utf-8'))
            self.assertEqual(secrets.get('vpn-'+profile['id']), key)
            service.remove(profile)
            self.assertEqual(service.profiles(), [])
            self.assertEqual(secrets.get('vpn-'+profile['id']), '')

    def test_windows_commands_receive_values_as_data(self):
        with patch('friday.vpn.subprocess.run', return_value=Mock(returncode=0, stdout='[]')) as run:
            VPN._ps('add', {'name': 'x;whoami', 'server': 'example.com', 'protocol': 'Ikev2'})
        self.assertNotIn('x;whoami', run.call_args.args[0][-1])
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['name'], 'x;whoami')

    def test_external_profile_cannot_claim_native_tunnel(self):
        service = VPN(Mock())
        with self.assertRaises(ValueError): service.connect({'kind': 'external'})
        with self.assertRaises(ValueError): service.disconnect({'kind': 'external'})


if __name__ == '__main__': unittest.main()
