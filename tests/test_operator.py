import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from friday.engine import Engine
from friday.storage import Store
from friday.operator import Skills, Tool, schema
from friday.web_access import public_url, WebAccess, Cancelled


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)); self.engine=Engine(self.store,Mock())
        self.op=self.engine.operator

    def test_disable_uninstall_and_reinstall_controls_real_tools(self):
        self.op.skills.change('browser','disable')
        result=self.op.registry.call('browser.search',{'query':'test'})
        self.assertFalse(result['ok'])
        self.assertNotIn('browser.search',self.op.registry.available())
        self.op.skills.change('browser','uninstall')
        self.assertNotIn('browser',Skills(self.store).state)
        self.op.skills.change('browser','install')
        self.assertTrue(Skills(self.store).enabled('browser'))
        self.assertIn('browser.read',self.op.registry.available())

    def test_unknown_tools_and_extra_parameters_are_rejected(self):
        self.assertFalse(self.op.registry.call('shell.exec',{'code':'x'})['ok'])
        self.assertFalse(self.op.registry.call('system.state',{'extra':'x'})['ok'])

    def test_high_permission_and_confirmation_expiry(self):
        action=Mock(return_value={'verified':True})
        self.op.registry.register(Tool('system.test','test','test',schema(), 'system','HIGH',action,lambda r:True,False))
        with patch.object(self.op,'model',return_value={'tool':'system.test','arguments':{}}):
            answer=self.op.run('состояние компьютера')
        self.assertIn('подтверждаю',answer); action.assert_not_called()
        self.op.pending['expires']=0
        self.assertIn('истекло',self.engine.execute('подтверждаю')); action.assert_not_called()

    def test_bounded_agent_uses_verified_tool_results(self):
        with patch.object(self.op,'model',side_effect=[{'tool':'system.processes','arguments':{}},{'final':'Список получен.'}]):
            self.assertEqual(self.op.run('покажи процессы'),'Список получен.')
        self.assertTrue((self.store.data/'logs/execution.jsonl').is_file())

    def test_web_context_cannot_call_computer_action(self):
        with patch.object(self.op,'model',side_effect=[{'tool':'files.open','arguments':{'path':'C:/secret.txt'}},{'final':'Открыто'}]):
            answer=self.op.run('найди в интернете инструкцию')
        self.assertIn('недоступен',answer)

    def test_automation_saves_and_runs_through_registry(self):
        steps=json.dumps([{'tool':'system.processes','arguments':{}}])
        result=self.op.registry.call('automation.create',{'name':'Проверка','steps':steps})
        self.assertTrue(result['verified'])
        self.assertTrue(self.op.registry.call('automation.run',{'name':'Проверка'})['confirmation_required'])
        self.assertTrue(self.op.registry.call('automation.run',{'name':'Проверка'},approved=True)['verified'])
        self.op.skills.change('system','disable')
        self.assertFalse(self.op.registry.call('automation.run',{'name':'Проверка'},approved=True)['ok'])

    def test_cancel_prevents_next_tool(self):
        self.op.stop()
        result=self.op.registry.call('system.state',{})
        self.assertTrue(result['cancelled'])

    def test_browser_confirmation_is_bound_to_page(self):
        with patch.object(self.op.browser,'current',return_value={'id':'one','url':'https://example.org/'}):
            self.assertIn('подтверждаю',self.engine.execute('браузер нажми Test'))
        with patch.object(self.op.browser,'current',return_value={'id':'one','url':'https://different.example/'}), \
                patch.object(self.op.registry,'call') as call:
            self.assertIn('изменилась',self.engine.execute('подтверждаю'))
            call.assert_not_called()

    def test_waiting_for_ollama_can_be_cancelled(self):
        entered=threading.Event(); release=threading.Event(); outcome=[]
        def slow(*args):
            entered.set(); release.wait(2); return 'late'
        def invoke():
            try:
                self.op.model([])
            except Cancelled:
                outcome.append('cancelled')
        with patch.object(self.op,'_model',side_effect=slow):
            caller=threading.Thread(target=invoke)
            caller.start(); self.assertTrue(entered.wait(1))
            self.op.stop(); caller.join(1)
            self.assertEqual(outcome,['cancelled'])
            release.set()

    def test_internet_off_prevents_search(self):
        self.store.config['web_enabled']=False
        with patch.object(self.op.web,'fetch') as fetch:
            self.assertIn('выключен',self.engine.execute('найди в интернете погоду'))
            fetch.assert_not_called()

    def test_summary_uses_only_real_source_urls(self):
        search={'query':'x','results':[{'title':'Source','url':'https://example.org/','snippet':'Data'}]}
        with patch.object(self.op.web,'fetch'), patch.object(self.op.registry,'call',side_effect=[
                {'tool':'browser.search','ok':True,'result':search},
                {'tool':'browser.read','ok':False,'error':'blocked'}]), \
                patch.object(self.op,'model',return_value='Сведения [1]. https://invented.example/test'):
            answer=self.op.research('x')
        self.assertIn('https://example.org/',answer)
        self.assertNotIn('https://invented.example',answer)


class WebTests(unittest.TestCase):
    def test_private_protocols_and_addresses_are_rejected(self):
        for url in ('file:///C:/secret','javascript:alert(1)','https://user:password@example.com','http://127.0.0.1:11435'):
            with self.assertRaises(ValueError):
                public_url(url)
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('192.168.1.1',443))]):
            with self.assertRaises(ValueError):
                public_url('https://example.com/')

    def test_text_extraction_does_not_include_scripts(self):
        web=WebAccess()
        body=b'<html><head><title>Example</title></head><body><script>SECRET_SCRIPT</script><main>'+b'Public article. '*20+b'</main></body></html>'
        with patch.object(web,'fetch',return_value=('https://example.com/',body,'text/html')):
            result=web.read('https://example.com/')
        self.assertEqual(result['title'],'Example')
        self.assertNotIn('SECRET_SCRIPT',result['text'])
        web.cancel.set()
        with self.assertRaises(Cancelled):
            web.read('https://example.com/')


if __name__=='__main__':
    unittest.main()
