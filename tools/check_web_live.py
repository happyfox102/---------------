"""Explicit real-network check; no camera, microphone, or browser interaction."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from friday.engine import Engine
from friday.storage import Store

def main():
    engine=Engine(Store(ROOT))
    report={}
    try:
        answer=engine.execute('найди в интернете Python official documentation')
        report={'answer':answer,'sources':engine.operator.sources,'model':engine.store.config['ollama_model'],
                'ok':bool(engine.operator.sources) and 'Источники:' in answer and 'не смог' not in answer}
    except Exception as exc:
        report={'ok':False,'error':str(exc)}
    (ROOT/'artifacts/web-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['ok'] else 1

if __name__=='__main__':
    sys.exit(main())
