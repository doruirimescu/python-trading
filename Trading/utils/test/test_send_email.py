import unittest
from Trading.utils.send_email import send_email, send_email_if_exception_occurs
"""
1. Setup a .env file with the following:
EMAIL_SENDER="sender@gmail.com"
EMAIL_PASSWORD="app password set in gmail settings"
EMAIL_RECIPIENTS=["recipient@gmail.com"]

2. Set SHOULD_SEND_EMAIL to True
3. Run tests
4. Check your email
"""

SHOULD_SEND_EMAIL = False


class TestSendEmail(unittest.TestCase):
    def test_send_email(self):
        if SHOULD_SEND_EMAIL is True:
            send_email(subject="TestSendEmail", body="This e-mail was generated from a python test")

    def test_send_email_if_exception_occurs(self):
        @send_email_if_exception_occurs("TestSendEmail")
        def exception_throwing_method(n):
            if n < 1000:
                raise Exception("Test exception throwing method")

        if SHOULD_SEND_EMAIL is True:
            exception_throwing_method(10)
