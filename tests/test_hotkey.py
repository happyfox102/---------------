import unittest
from friday.hotkey import DoublePress


class HotkeyTests(unittest.TestCase):
    def test_double_press_and_held_key(self):
        detector = DoublePress()
        self.assertFalse(detector.feed(True, True, 1))
        self.assertFalse(detector.feed(True, True, 1.1))
        detector.feed(False, True, 1.2)
        self.assertTrue(detector.feed(True, True, 1.3))
        detector.feed(False, True, 1.4)
        self.assertFalse(detector.feed(True, True, 1.5))

    def test_timeout_and_missing_control(self):
        detector = DoublePress()
        self.assertFalse(detector.feed(True, True, 1))
        detector.feed(False, True, 1.1)
        self.assertFalse(detector.feed(True, True, 2))
        detector.feed(False, True, 2.1)
        self.assertFalse(detector.feed(True, False, 2.2))
        detector.feed(False, False, 2.3)
        self.assertFalse(detector.feed(True, True, 2.4))
