import threading
from .qt import QtWidgets as W, Signal
from .design import LoadingBar
from .credentials import Secrets

class AISettings(W.QWidget):
    checked = Signal(str)
    def __init__(self, store):
        super().__init__(); self.store=store; f=W.QFormLayout(self)
        self.provider=W.QComboBox()
        for title,value in [('Ollama (локально)','ollama'),('OpenAI','openai'),('Gemini (Google)','gemini'),('Groq (быстрый)','groq')]: self.provider.addItem(title,value)
        self.provider.setCurrentIndex(max(0,self.provider.findData(store.config.get('ai_provider','ollama')))); f.addRow('Провайдер',self.provider)
        self.model=W.QLineEdit(store.config.get('openai_model','gpt-4.1-mini')); f.addRow('Модель OpenAI',self.model)
        self.gemini=W.QLineEdit(store.config.get('gemini_model','gemini-flash-latest')); f.addRow('Модель Gemini',self.gemini)
        groq_model=store.config.get('groq_model','openai/gpt-oss-20b')
        if groq_model in ('llama-3.3-70b-versatile','llama-3.1-8b-instant'): groq_model='openai/gpt-oss-20b'
        self.groq=W.QLineEdit(groq_model); f.addRow('Модель Groq',self.groq)
        self.key=W.QLineEdit(); self.key.setEchoMode(W.QLineEdit.EchoMode.Password); f.addRow('API-ключ провайдера',self.key)
        self.remove=W.QCheckBox('Удалить сохранённый ключ'); f.addRow(self.remove)
        self.check=W.QPushButton('Проверить выбранный ИИ'); self.check.clicked.connect(self.test); f.addRow(self.check)
        self.progress=LoadingBar(); f.addRow(self.progress); self.status=W.QLabel('Ключ хранится в защищённом хранилище Windows.'); self.status.setWordWrap(True); f.addRow(self.status); self.checked.connect(self.finished)
    def values(self): return {'ai_provider':self.provider.currentData(),'openai_model':self.model.text().strip(),'gemini_model':self.gemini.text().strip(),'groq_model':self.groq.text().strip()}
    def save_secret(self):
        n=self.provider.currentData()
        if self.remove.isChecked(): Secrets().delete(n)
        elif self.key.text().strip(): Secrets().set(n,self.key.text().strip())
        self.key.clear()
    def test(self):
        c=self.values(); k=self.key.text().strip() or None; self.check.setEnabled(False); self.progress.loading(True)
        def work():
            try:
                if k: Secrets().set(c['ai_provider'],k)
                if c['ai_provider']=='gemini':
                    from .gemini_ai import complete; complete(c,[{'role':'user','content':'готово'}])
                else:
                    from .cloud_ai import complete; complete(c,[{'role':'user','content':'готово'}],key=k)
                msg=f'{self.provider.currentText()} отвечает. Сохраните настройки.'
            except Exception as e: msg=str(e)
            self.checked.emit(msg)
        threading.Thread(target=work,daemon=True).start()
    def finished(self,msg): self.check.setEnabled(True); self.progress.loading(False); self.status.setText(msg)
