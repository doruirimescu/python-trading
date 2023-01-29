import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from typing import List
import functools
import json


def send_email(subject: str, body: str):
    load_dotenv()
    sender = os.environ("EMAIL_SENDER")
    password = os.environ("EMAIL_PASSWORD")
    recipients = json.loads(os.environ["EMAIL_RECIPIENTS"])

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(sender, password)
    smtp_server.sendmail(sender, recipients, msg.as_string())
    smtp_server.quit()


def send_email_if_exception_occurs(subject: str = "Exception occurred"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                import traceback
                body = f"Exception {e} occurred when executing function: {func.__name__} \
                        \n{traceback.format_exc()}"
                send_email(subject, body)
        return wrapper
    return decorator

# from exception_with_retry import exception_with_retry
# @send_email_if_exception_occurs()
# @exception_with_retry(n_retry=5, sleep_time_s=1)
# def myMethod(n: int):
#     print(f"Got  {str(n)}")
#     if n < 0:
#         raise Exception("Some exception stuff")
#     else:
#         return 1

# myMethod(-1)
# subject = "Email Subject"
# body = "This is the body of the text message"
# send_email(subject, body)
