import unittest
from Trading.utils.data_processor import JsonFileProcessor

class TestJsonFileProcessor(unittest.TestCase):
    def test_read_json_file(self):
        processor = JsonFileProcessor("test.json")
        self.assertEqual(processor.data, {})
