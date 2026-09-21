"""Provision user-authorized credentials through hidden input, never command arguments."""
import getpass
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from friday.credentials import Secrets
from friday.storage import Store
from friday.vpn import VPN

key = getpass.getpass('OpenAI key (hidden): ').strip().replace('\\_', '_')
subscription = getpass.getpass('VPN subscription (hidden): ').strip()
secrets = Secrets()
if key:
    if not key.startswith('sk-') or any(c.isspace() for c in key):
        raise SystemExit('Invalid key shape')
    secrets.set('openai', key)
if subscription:
    secrets.set('vpn-subscription', subscription)
for root in (ROOT, ROOT/'dist/Пятница'):
    store = Store(root)
    if subscription:
        vpn = VPN(store)
        if not any(p['name'] == 'Моя подписка' for p in vpn.profiles()):
            vpn.import_key('Моя подписка', subscription)
    if key:
        config = store.config.copy(); config.update(ai_provider='openai', openai_model='gpt-4.1-mini')
        store.save_config(config)
print('Credentials encrypted; source and portable settings configured.', flush=True)
