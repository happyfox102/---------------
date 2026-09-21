"""Dedicated Edge session via CDP; never attaches to the user's existing tabs."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import requests
from .web_access import public_url, Cancelled


class BrowserControl:
    def __init__(self,store,cancel):
        self.store,self.cancel=store,cancel
        self.process=None; self.port=None; self.target=None
        self.session=requests.Session(); self.session.trust_env=False

    def start(self):
        if self.process and self.process.poll() is None:
            return
        candidates=[Path(os.environ.get(env,''))/'Microsoft/Edge/Application/msedge.exe'
                    for env in ('PROGRAMFILES(X86)','PROGRAMFILES','LOCALAPPDATA')]
        executable=next((p for p in candidates if p.is_file()),None)
        if not executable:
            raise ValueError('Для управления вкладками нужен Microsoft Edge. Поиск и чтение публичных сайтов доступны отдельно.')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); self.port=sock.getsockname()[1]
        self.process=subprocess.Popen([str(executable),f'--remote-debugging-port={self.port}',
            '--remote-debugging-address=127.0.0.1',f'--user-data-dir={self.store.data / "browser-profile"}',
            '--no-first-run','--no-default-browser-check','about:blank'],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if self.cancel.is_set():
                raise Cancelled('Задача остановлена.')
            try:
                self.targets(); return
            except requests.RequestException:
                self.cancel.wait(.2)
        raise TimeoutError('Edge не включил управление вкладками за 15 секунд.')

    def targets(self):
        if not self.port:
            raise ValueError('Сначала откройте управляемый браузер.')
        result=self.session.get(f'http://127.0.0.1:{self.port}/json/list',timeout=3)
        result.raise_for_status()
        return [item for item in result.json() if item.get('type')=='page']

    def current(self):
        pages=self.targets()
        page=next((p for p in pages if p['id']==self.target),None)
        if page is None:
            raise ValueError('Активной управляемой вкладки нет. Откройте страницу командой «браузер открой URL».')
        return page

    def cdp(self,method,params=None,page=None):
        import websocket
        if self.cancel.is_set():
            raise Cancelled('Задача остановлена.')
        page=page or self.current()
        connection=websocket.create_connection(page['webSocketDebuggerUrl'],timeout=8,suppress_origin=True,
                                              http_no_proxy=['127.0.0.1','localhost'])
        try:
            connection.send(json.dumps({'id':1,'method':method,'params':params or {}}))
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if self.cancel.is_set():
                    raise Cancelled('Задача остановлена.')
                answer=json.loads(connection.recv())
                if answer.get('id')==1:
                    if 'error' in answer:
                        raise ValueError(answer['error'].get('message','Ошибка браузера'))
                    return answer.get('result',{})
            raise TimeoutError('Браузер не ответил.')
        finally:
            connection.close()

    def evaluate(self,expression):
        # Only application-authored expressions; no arbitrary JavaScript tool exists.
        result=self.cdp('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):
            raise ValueError('Не удалось прочитать страницу.')
        return result.get('result',{}).get('value')

    def open(self,url):
        public_url(url); self.start()
        response=self.session.put(f'http://127.0.0.1:{self.port}/json/new?about:blank',timeout=5)
        response.raise_for_status(); page=response.json(); self.target=page['id']
        self.cdp('Page.navigate',{'url':url},page)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if self.cancel.is_set():
                raise Cancelled('Задача остановлена.')
            result=self.evaluate('({url:location.href,title:document.title,ready:document.readyState})')
            if result and result.get('url','').startswith(('http://','https://')) and result.get('ready')=='complete':
                return dict(result,verified=True)
            self.cancel.wait(.3)
        return {'url':url,'verified':False,'verification':'Вкладка создана, но загрузка за 20 секунд не подтверждена.'}

    def read(self):
        page=self.current()
        if not page['url'].startswith(('http://','https://')):
            raise ValueError('Разрешено чтение только веб-страниц управляемого браузера.')
        public_url(page['url'])
        result=self.evaluate('({url:location.href,title:document.title,text:(document.body?.innerText || "").slice(0,14000)})')
        return result

    def find(self,text):
        self.read()  # Validate the current origin, never an internal/file page.
        query=json.dumps(text,ensure_ascii=False)
        return self.evaluate('''(()=>{const q=QUERY.toLowerCase(); return [...document.querySelectorAll('a,button,input,textarea,select,[role="button"]')]
            .map((e,i)=>({index:i,text:(e.innerText||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').trim(),tag:e.tagName,
            box:e.getBoundingClientRect().toJSON()})).filter(e=>e.text.toLowerCase().includes(q)&&e.box.width>0&&e.box.height>0).slice(0,15)})()'''.replace('QUERY',query))

    def interact(self,text,value=None):
        self.read()
        before=self.evaluate('({url:location.href,text:(document.body?.innerText || "").slice(0,14000)})')
        action='e.click();' if value is None else 'if(!["INPUT","TEXTAREA"].includes(e.tagName)||e.type==="password")return {error:"Нельзя заполнить этот элемент"}; e.focus(); const setter=Object.getOwnPropertyDescriptor(e.tagName==="INPUT"?HTMLInputElement.prototype:HTMLTextAreaElement.prototype,"value").set; setter.call(e,value); e.dispatchEvent(new Event("input",{bubbles:true})); e.dispatchEvent(new Event("change",{bubbles:true}));'
        expression='''((query,value)=>{const q=query.toLowerCase();const nodes=[...document.querySelectorAll('a,button,input,textarea,[role="button"]')].filter(e=>
            (e.innerText||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').trim().toLowerCase()===q&&e.getBoundingClientRect().width>0);
            if(nodes.length!==1)return {error:"Нужно одно точное совпадение подписи. Найдено: "+nodes.length};const e=nodes[0];
            ACTION return {sent:true};})'''.replace('ACTION',action)+'('+json.dumps(text,ensure_ascii=False)+','+json.dumps(value,ensure_ascii=False)+')'
        result=self.evaluate(expression)
        if result.get('error'):
            raise ValueError(result['error'])
        self.cancel.wait(.7)
        after=self.evaluate('({url:location.href,text:(document.body?.innerText || "").slice(0,14000),value:document.activeElement?.value})')
        changed=bool(after and (after.get('url')!=before['url'] or after.get('text')!=before['text']))
        verified=after.get('value')==value if value is not None else changed
        return {'verified':verified,'verification':'Изменение страницы подтверждено.' if verified else 'Действие отправлено, но изменение страницы не обнаружено.','url':after.get('url')}

    def close_tab(self):
        page=self.current(); self.cdp('Page.close')
        self.cancel.wait(.2)
        return {'verified':not any(p['id']==page['id'] for p in self.targets())}
