import unittest
from datetime import datetime
from friday.child_policy import decision, schedule_allowed, set_pin, check_pin


class ChildPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = {'security_allowed_sites':['example.com'], 'security_blocked_sites':['bad.example.com']}

    def test_domain_boundaries_and_redirect_targets(self):
        self.assertTrue(decision('https://www.example.com/a',self.config)[0])
        for url in ['https://example.com.attacker.test', 'https://bad.example.com',
                    'https://sub.bad.example.com', 'file:///C:/private.txt',
                    'https://unknown.test', 'http://example.com', 'https://a:b@example.com']:
            self.assertFalse(decision(url,self.config)[0],url)

    def test_schedule_normal_and_overnight(self):
        self.assertTrue(schedule_allowed('22:00','06:00',datetime(2026,1,1,23)))
        self.assertFalse(schedule_allowed('22:00','06:00',datetime(2026,1,1,12)))
        self.assertFalse(schedule_allowed('09:00','21:00',datetime(2026,1,1,21)))
        self.assertFalse(schedule_allowed('bad','21:00'))

    def test_pin_is_salted_and_verified(self):
        first, second = set_pin('128934'), set_pin('128934')
        self.assertNotEqual(first,second)
        self.assertTrue(check_pin('128934',first))
        self.assertFalse(check_pin('000000',first))
        self.assertFalse(check_pin('000000','invalid'))
