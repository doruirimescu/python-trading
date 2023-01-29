import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from typing import List
import functools


def send_email(subject: str, body: str, recipients: List[str]):
    load_dotenv()
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(sender, password)
    smtp_server.sendmail(sender, recipients, msg.as_string())
    smtp_server.quit()


def send_email_if_exception_occurs(subject: str = "Exception occurred",
                                   recipients: List = []):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                import traceback
                body = f"Exception {e} occurred when executing function: {func.__name__} \
                        \n{traceback.format_exc()}"
                send_email(subject, body, recipients)
        return wrapper
    return decorator

# @send_email_if_exception_occurs(recipients=["recipient@gmail.com"])
# def myMethod(n: int):
#     print(f"Got  {n}")
#     if n < 0:
#         raise Exception("Some exception stuff")
#     else:
#         return 1

# subject = "Email Subject"
# body = "This is the body of the text message"
# recipients = ["recipient@gmail.com"]
# send_email(subject, body, recipients)
