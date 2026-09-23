import json
import tempfile
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

from friday.security import SecurityService
from friday.storage import Store


class SecurityTests(unittest.TestCase):
    def test_baseline_is_not_reported_as_new_launches(self):
        with tempfile.TemporaryDirectory() as temp:
            service = SecurityService(Store(Path(temp)))
            old = Mock(info={'pid':1,'name':'old.exe'})
            new = Mock(info={'pid':2,'name':'new.exe'})
            with patch('friday.security.psutil.process_iter', return_value=[old]):
                service.poll_processes()
            self.assertEqual(service.recent(), [])
            with patch('friday.security.psutil.process_iter', return_value=[new]):
                service.poll_processes()
            self.assertEqual([x['kind'] for x in service.recent()], ['app_closed','app_started'])

    def test_local_event_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            service = SecurityService(Store(Path(temp)))
            service.event("watch_started")
            service.event("app_started", app="example.exe", pid=42)
            report = service.build_report()
            text = report.read_text(encoding="utf-8")
            self.assertIn("example.exe", text)
            rows = [json.loads(x) for x in service.events.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["kind"], "watch_started")


if __name__ == "__main__":
    unittest.main()
