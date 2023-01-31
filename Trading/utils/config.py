from dotenv import load_dotenv
import os

load_dotenv()

USERNAME = os.getenv("XTB_USERNAME")
PASSWORD = os.getenv("XTB_PASSWORD")
MODE = os.getenv("XTB_MODE")
TIMEZONE = os.getenv("BROKER_TIMEZONE", 'Europe/Berlin')
