import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from friday.engine import Engine
from friday.storage import Store
from friday.apps import AppChoices
from friday.intent import canonical


class SystemCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.windows = Mock()
        self.windows.brightness.return_value = 50
        self.engine = Engine(self.store, self.windows)

    def test_polite_application_requests(self):
        for phrase in ("открой мне диспетчер задач", "можешь открыть диспетчер задач", "пожалуйста можешь открыть диспетчер задач", "открой, пожалуйста, диспетчер задач", "запусти приложение диспетчер задач"):
            self.engine.execute(phrase)
            self.windows.open_app.assert_called_with("диспетчер задач", self.store.config)

    def test_missing_folder_name_prompts_then_opens(self):
        self.assertIn("Какую папку", self.engine.execute("открой мне папку"))
        with patch.object(self.engine, "open_named", return_value="Открываю") as opened:
            self.engine.execute("Код")
            opened.assert_called_once_with("Код", "folder")

    def test_brightness_relative_absolute_and_bounds(self):
        self.engine.execute("спусти яркость")
        self.windows.brightness.assert_called_with(delta=-10)
        self.engine.execute("подними яркость на двадцать процентов")
        self.windows.brightness.assert_called_with(delta=20)
        self.engine.execute("установи яркость 50 процентов")
        self.windows.brightness.assert_called_with(value=50)
        self.windows.brightness.reset_mock()
        self.assertIn("от 0 до 100", self.engine.execute("яркость 101"))
        self.windows.brightness.assert_not_called()

    def test_screen_and_window_capture(self):
        self.engine.execute("сделай скриншот")
        self.assertFalse(self.windows.screenshot.call_args.kwargs["active"])
        self.engine.execute("сделай, пожалуйста, скриншот приложения")
        self.assertTrue(self.windows.screenshot.call_args.kwargs["active"])
        path = self.windows.screenshot.call_args.args[0]
        self.assertEqual(path.parent, self.store.data / "screenshots")

    def test_power_modes(self):
        for phrase, mode in (("включить энергосбережения питания", "saver"), ("включи производительность", "performance"), ("выключи энергосбережение", "balanced")):
            self.engine.execute(phrase)
            self.windows.power_mode.assert_called_with(mode)

    def test_program_choice(self):
        entries = [{"name": "A", "target": "a.exe"}, {"name": "B", "target": "b.exe"}]
        self.windows.open_app.side_effect = AppChoices(entries)
        self.assertIn("номер", self.engine.execute("открой редактор"))
        self.windows.catalog.launch.assert_not_called()
        self.engine.execute("два")
        self.windows.catalog.launch.assert_called_once_with(entries[1])

    def test_ai_route_is_bounded_and_does_not_recurse(self):
        self.store.config["ollama_model"] = "test"
        with patch("friday.intent.interpret", return_value="подними яркость на 10"):
            self.engine.execute("сделай экран чуть светлее")
            self.windows.brightness.assert_called_once_with(delta=10)
        self.windows.open_app.side_effect = ValueError("missing")
        with patch("friday.intent.interpret", return_value="открой missing") as route:
            self.engine.execute("открой неизвестное")
            route.assert_called_once()

    def test_untrusted_ai_payloads_are_rejected(self):
        for intent in ({"action": "shutdown"}, {"action": "shell", "value": "calc"}, {"action": "open_app", "value": "C:\\evil.exe"}, {"action": "brightness_set", "value": 101}, {"action": "brightness_set", "value": True}):
            self.assertIsNone(canonical(intent))
        self.assertEqual(canonical({"action": "power_mode", "value": "saver"}), "включи энергосбережение")
