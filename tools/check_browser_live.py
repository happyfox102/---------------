"""Smoke test against public example.com; all tabs belong to Friday's profile."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from friday.engine import Engine
from friday.storage import Store

def main():
    engine=Engine(Store(ROOT)); browser=engine.operator.browser; report={}
    try:
        opened=engine.execute('браузер открой https://example.com/')
        page=browser.read()
        assert 'Example Domain' in page['text'],page
        found=browser.find('Learn more') or browser.find('More information')
        assert found,'Link not found'
        label=found[0]['text']
        confirmation=engine.execute('браузер нажми '+label)
        assert 'подтверждаю' in confirmation
        clicked=engine.execute('подтверждаю')
        after=browser.read()
        assert 'iana.org' in after['url'],after
        report={'ok':True,'opened':opened,'page':page['title'],'found':label,'click':clicked,'verified_url':after['url']}
        browser.open('https://www.python.org/')
        field=browser.find('Search')
        assert field,'Search field not found'
        typed=browser.interact('Search','Friday test')
        assert typed['verified'],typed
        report['input_verified']=True
    except Exception:
        import traceback
        report={'ok':False,'error':traceback.format_exc()}
    finally:
        try:
            browser.cdp('Browser.close')
        except Exception:
            pass
    (ROOT/'artifacts/browser-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['ok'] else 1

if __name__=='__main__':
    sys.exit(main())
