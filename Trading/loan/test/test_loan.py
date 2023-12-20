import unittest
import Trading.loan.loan as loan


class LoanTest(unittest.TestCase):
    def test_loan_total(self):
        ljp = loan.LoanJsonParser(json_path="test/example.json")
        self.assertEqual(ljp.principal_paid(), 225)
