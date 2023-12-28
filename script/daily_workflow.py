from Trading.utils.send_email import send_email
from Trading.config.config import GENERATED_PATH

# Generate daily analysis report
# For each file in GENERATED_PATH, add them to attachments list
attachments = []
for file in GENERATED_PATH.iterdir():
    # only .png files
    if file.suffix == ".png":
        attachments.append(str(file))
print(attachments)
send_email(
    subject="Email from github action",
    body="This e-mail was generated from a python test",
    attachments=attachments,
)
