import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import List
import functools
import json


def send_email(subject: str, body: str, attachments: List[str] = None):
    load_dotenv()
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    recipients = json.loads(os.environ["EMAIL_RECIPIENTS"])

    msg = MIMEMultipart(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(body, 'plain'))

    # Attach attachments
    if attachments:
        for path in attachments:
            with open(path, "rb") as image_file:
                img = MIMEImage(image_file.read())
                img.add_header('Content-Disposition', 'attachment', filename=path)
                msg.attach(img)

    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(sender, password)
    smtp_server.sendmail(sender, recipients, msg.as_string())
    smtp_server.quit()


def send_email_if_exception_occurs(subject: str = "Exception occurred"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                import traceback
                body = f"Exception {e} occurred when executing function: {func.__name__} \
                        \n{traceback.format_exc()}"
                send_email(subject, body)
                raise e
        return wrapper
    return decorator
