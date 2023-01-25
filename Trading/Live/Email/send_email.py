import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText


def send_email(subject, body, recipients):
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



# subject = "Email Subject"
# body = "This is the body of the text message"
# recipients = ["dorustefan.irimescu@gmail.com"]
# send_email(subject, body, recipients)
