from Trading.utils.send_email import send_email
from Trading.config.config import GENERATED_PATH

BODY = "This e-mail was generated automatically by the daily workflow script."

#! Handle alerts
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.live.alert.alert import get_top_ten_biggest_swaps_report
from Trading.live.client.client import XTBLoggingClient

client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)
body, _ = get_top_ten_biggest_swaps_report(client)
BODY += "\n\n" + body


# Generate daily analysis report
# For each file in GENERATED_PATH, add them to attachments list
attachments = []
for file in GENERATED_PATH.iterdir():
    # only .png files
    if file.suffix == ".png":
        attachments.append(str(file))


send_email(
    subject="Daily trading workflow report",
    body=BODY,
    attachments=attachments,
)
