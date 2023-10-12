import unittest
import json
import loan
from pathlib import Path
import os
# get current file path
CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))


with open(CURRENT_FILE_PATH.joinpath("example.json")) as f:
    TEST_DATA = json.load(f)

class LoanTest(unittest.TestCase):
    def test_loan_total(self):
        self.assertEqual(loan.principal_paid(TEST_DATA), 225)
