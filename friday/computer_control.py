"""Bounded Win32 mouse, keyboard and window controls for the operator."""
import ctypes
import os
import re
import time


class ComputerControl:
    MAX_TEXT = 4000

    def __init__(self, vision, cancel):
        self.vision, self.cancel = vision, cancel

    def _check(self):
        if self.cancel.is_set():
            raise RuntimeError('Задача остановлена.')
        if os.name != 'nt':
            raise RuntimeError('Управление компьютером доступно только в Windows.')

    def _point(self, x, y):
        self._check()
        try:
            x, y = int(x), int(y)
        except (TypeError, ValueError):
            raise ValueError('Координаты должны быть целыми числами.')
        if not (0 <= x <= 10000 and 0 <= y <= 10000):
            raise ValueError('Координаты вне безопасного диапазона экрана.')
        import win32api
        width, height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError('Точка находится за пределами экрана.')
        return x, y

    def move(self, x, y):
        x, y = self._point(x, y)
        import win32api
        win32api.SetCursorPos((x, y))
        return {'x':x, 'y':y, 'verified':win32api.GetCursorPos() == (x,y)}

    def click(self, x, y, button='left', count=1):
        x, y = self._point(x, y)
        import win32api, win32con
        win32api.SetCursorPos((x,y))
        down, up = (win32con.MOUSEEVENTF_LEFTDOWN,win32con.MOUSEEVENTF_LEFTUP) if button=='left' else (win32con.MOUSEEVENTF_RIGHTDOWN,win32con.MOUSEEVENTF_RIGHTUP)
        for _ in range(count):
            win32api.mouse_event(down,0,0,0,0); win32api.mouse_event(up,0,0,0,0)
            if count > 1: time.sleep(.08)
        return {'x':x,'y':y,'button':button,'clicks':count,'verified':False,
                'verification':'Курсор установлен, событие мыши отправлено.'}

    def drag(self, x1, y1, x2, y2):
        start=self._point(x1,y1); end=self._point(x2,y2)
        import win32api, win32con
        win32api.SetCursorPos(start); win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
        try:
            for step in range(1, 11):
                self._check()
                win32api.SetCursorPos(tuple(round(a+(b-a)*step/10) for a,b in zip(start,end)))
                self.cancel.wait(.02)
        finally:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0,0,0)
        return {'from':start,'to':end,'verified':False,'verification':'События перетаскивания отправлены; результат приложения не проверен.'}

    def scroll(self, amount):
        try: amount=int(amount)
        except (TypeError,ValueError): raise ValueError('Прокрутка должна быть целым числом.')
        if not -20 <= amount <= 20 or amount==0: raise ValueError('Прокрутка: от -20 до 20 шагов.')
        self._check(); import win32api
        win32api.mouse_event(0x0800,0,0,amount*120,0)
        return {'steps':amount,'verified':False,'verification':'Прокрутка отправлена; содержимое окна не проверено.'}

    def type_text(self, text):
        self._check(); text=str(text)
        if not text or len(text)>self.MAX_TEXT or '\x00' in text: raise ValueError('Текст пустой или слишком длинный.')
        if re.search(r'парол|password|cvv|cvc|секрет|токен',text,re.I): raise ValueError('Ввод паролей, токенов и секретов запрещён.')
        from .desktop_access import focused
        element = focused()
        if element['password']:
            raise ValueError('Ввод в защищённое поле запрещён.')
        import win32gui
        target = win32gui.GetForegroundWindow()
        for char in text:
            self._check()
            if win32gui.GetForegroundWindow() != target:
                raise ValueError('Активное окно изменилось; ввод остановлен.')
            self._unicode(char)
        return {'length':len(text),'verified':False,'verification':'Текст отправлен активному полю; содержимое после ввода не проверено.'}

    def _unicode(self,char):
        from ctypes import wintypes as T
        class Keyboard(ctypes.Structure):
            _fields_ = [('vk',T.WORD),('scan',T.WORD),('flags',T.DWORD),('time',T.DWORD),('extra',ctypes.c_size_t)]
        class Mouse(ctypes.Structure):
            _fields_ = [('x',T.LONG),('y',T.LONG),('data',T.DWORD),('flags',T.DWORD),('time',T.DWORD),('extra',ctypes.c_size_t)]
        class Data(ctypes.Union):
            _fields_ = [('keyboard',Keyboard),('mouse',Mouse)]
        class Input(ctypes.Structure):
            _fields_ = [('type',T.DWORD),('data',Data)]
        units = char.encode('utf-16-le')
        events = []
        for index in range(0,len(units),2):
            scan = int.from_bytes(units[index:index+2], 'little')
            for flags in (4,6): events.append(Input(1,Data(keyboard=Keyboard(0,scan,flags,0,0))))
        array = (Input * len(events))(*events)
        if ctypes.windll.user32.SendInput(len(events),array,ctypes.sizeof(Input)) != len(events):
            raise ValueError('Windows заблокировала ввод в это приложение.')

    def press(self,key):
        self._check(); import win32api, win32con
        names={'enter':win32con.VK_RETURN,'return':win32con.VK_RETURN,'esc':win32con.VK_ESCAPE,'escape':win32con.VK_ESCAPE,
               'tab':win32con.VK_TAB,'backspace':win32con.VK_BACK,'space':win32con.VK_SPACE,'up':win32con.VK_UP,'down':win32con.VK_DOWN,
               'left':win32con.VK_LEFT,'right':win32con.VK_RIGHT,'home':win32con.VK_HOME,'end':win32con.VK_END,'delete':win32con.VK_DELETE}
        value=names.get(str(key).casefold())
        if value is None and re.fullmatch(r'f(?:[1-9]|1[0-2])',str(key).casefold()): value=getattr(win32con,'VK_'+str(key).upper())
        if value is None: raise ValueError('Разрешена только безопасная клавиша навигации.')
        win32api.keybd_event(value,0,0,0); win32api.keybd_event(value,0,win32con.KEYEVENTF_KEYUP,0)
        return {'key':key,'verified':False,'verification':'Клавиша отправлена; результат в приложении не проверен.'}

    def hotkey(self, keys):
        values=[str(v).strip().casefold() for v in str(keys).split('+')]
        if not 2<=len(values)<=4: raise ValueError('Горячая клавиша должна содержать от 2 до 4 клавиш.')
        allowed={'ctrl':0x11,'control':0x11,'shift':0x10,'alt':0x12,'win':0x5B,'tab':0x09,'c':0x43,'v':0x56,'x':0x58,'z':0x5A,'s':0x53,'a':0x41,'f4':0x73,'esc':0x1B}
        if any(v not in allowed for v in values): raise ValueError('Эта комбинация клавиш запрещена.')
        self._check(); import win32api, win32con
        pressed = []
        try:
            for v in values:
                self._check(); win32api.keybd_event(allowed[v],0,0,0); pressed.append(v)
        finally:
            for v in reversed(pressed): win32api.keybd_event(allowed[v],0,win32con.KEYEVENTF_KEYUP,0)
        return {'keys':'+'.join(values),'verified':False,'verification':'Комбинация отправлена; результат в приложении не проверен.'}

    def wait(self, seconds):
        try: seconds=float(seconds)
        except (TypeError,ValueError): raise ValueError('Время ожидания должно быть числом.')
        if not 0.05 <= seconds <= 30: raise ValueError('Ожидание: от 0.05 до 30 секунд.')
        if self.cancel.wait(seconds): raise RuntimeError('Задача остановлена.')
        return {'seconds':seconds,'verified':True}

    def focus(self, text):
        matches=self.vision.find_window(text)
        if len(matches)!=1: raise ValueError('Нужно ровно одно окно с таким заголовком.')
        import win32gui
        hwnd=matches[0]['handle']; win32gui.ShowWindow(hwnd,9); win32gui.SetForegroundWindow(hwnd)
        return {'title':matches[0]['title'],'verified':win32gui.GetForegroundWindow()==hwnd}

    def window_action(self, text, action):
        matches=self.vision.find_window(text)
        if len(matches)!=1: raise ValueError('Нужно ровно одно окно с таким заголовком.')
        import win32gui
        hwnd=matches[0]['handle']; commands={'minimize':6,'maximize':3}
        if action in commands:
            win32gui.ShowWindow(hwnd,commands[action])
            verified = bool(win32gui.IsIconic(hwnd)) if action == 'minimize' else win32gui.GetWindowPlacement(hwnd)[1] == 3
        elif action=='close':
            win32gui.PostMessage(hwnd,0x0010,0,0); self.cancel.wait(.2)
            verified = not win32gui.IsWindow(hwnd)
        else: raise ValueError('Неизвестное действие окна.')
        return {'title':matches[0]['title'],'action':action,'verified':verified,'verification':'Событие отправлено окну.'}
