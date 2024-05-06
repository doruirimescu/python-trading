import unittest
from Trading.utils.data_processor import JsonFileRW

class TestJsonFileProcessor(unittest.TestCase):
    def test_read_json_file(self):
        processor = JsonFileRW("test.json")
        self.assertEqual(processor.data, {})
