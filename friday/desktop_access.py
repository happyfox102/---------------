"""Focused element metadata via Windows UI Automation; never reads passwords."""
def focused():
    import comtypes
    from comtypes.client import CreateObject, GetModule
    comtypes.CoInitialize()
    try:
        module = GetModule('UIAutomationCore.dll')
        automation = CreateObject('{FF48DBA4-60EF-4201-AA87-54103EEF594E}', interface=module.IUIAutomation)
        element = automation.GetFocusedElement()
        if not element: raise ValueError('Не найден активный элемент ввода.')
        password = bool(element.CurrentIsPassword)
        return {'password': password, 'name': '' if password else element.CurrentName,
                'process': element.CurrentProcessId, 'type': element.CurrentControlType}
    except Exception:
        raise ValueError('Не удалось проверить поле ввода через Windows UI Automation. Введите текст вручную.') from None
    finally:
        comtypes.CoUninitialize()
