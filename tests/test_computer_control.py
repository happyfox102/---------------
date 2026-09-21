import unittest
from unittest.mock import patch
from friday.computer_control import ComputerControl

class ComputerControlTests(unittest.TestCase):
    def setUp(self):
        self.cancel=__import__('threading').Event(); self.vision=unittest.mock.Mock()
        self.control=ComputerControl(self.vision,self.cancel)

    def test_text_rejects_secrets_before_platform_call(self):
        with self.assertRaises(ValueError): self.control.type_text('введи пароль password')

    def test_bounds_reject_invalid_points(self):
        with patch('os.name','nt'), patch('win32api.GetSystemMetrics',side_effect=[1920,1080]):
            with self.assertRaises(ValueError): self.control.move(1920,100)

    def test_wait_is_cancellable(self):
        self.cancel.set()
        with self.assertRaises(RuntimeError): self.control.wait(0.05)

    def test_focus_requires_single_window(self):
        self.vision.find_window.return_value=[]
        with self.assertRaises(ValueError): self.control.focus('editor')

    def test_hotkey_rejects_unknown_keys(self):
        with self.assertRaises(ValueError): self.control.hotkey('ctrl+alt+delete')

if __name__=='__main__': unittest.main()
