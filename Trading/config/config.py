from dotenv import load_dotenv
import os

load_dotenv()

# XTB configurations
USERNAME = os.getenv("XTB_USERNAME")
PASSWORD = os.getenv("XTB_PASSWORD")
MODE = os.getenv("XTB_MODE")
TIMEZONE = os.getenv("BROKER_TIMEZONE", 'Europe/Berlin')

# Email configurations
EMAIL_SENDER=os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD=os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENTS=os.getenv("EMAIL_RECIPIENTS")

# Program configurations
MONITOR_FOREX_TRADE_SWAPS_ONCE=os.getenv("MONITOR_FOREX_TRADE_SWAPS_ONCE")
DATA_STORAGE_PATH=os.getenv("DATA_STORAGE_PATH")
