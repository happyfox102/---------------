"""Real Ollama tool-loop check limited to reading system metrics."""
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from friday.engine import Engine
from friday.storage import Store

def main():
    source=Store(ROOT)
    with tempfile.TemporaryDirectory() as temp:
        store=Store(Path(temp)); store.config.update(ollama_url=source.config['ollama_url'],ollama_model=source.config['ollama_model'])
        engine=Engine(store)
        answer=engine.operator.run('Проверь текущее состояние компьютера: процессор и память. Используй system.state, затем кратко сообщи результат.')
        log=store.data/'logs/execution.jsonl'
        calls=[json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
        report={'answer':answer,'tools':[v['tool'] for v in calls],
                'ok':any(v['tool']=='system.state' and v['verified'] for v in calls)}
        (ROOT/'artifacts/operator-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
        return 0 if report['ok'] else 1

if __name__=='__main__':
    sys.exit(main())
