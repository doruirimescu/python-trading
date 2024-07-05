from unittest import TestCase
from Trading.utils.criterion.enableable import Enableable

class TestEnableable(TestCase):
    def test_enableable(self):
        enableable = Enableable()
        self.assertFalse(enableable.is_enabled)
        enableable.enable()
        self.assertTrue(enableable.is_enabled)
        enableable.disable()
        self.assertFalse(enableable.is_enabled)
