from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))

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
DATA_STORAGE_PATH=os.getenv("DATA_STORAGE_PATH", "./Trading/live/scripts/data/")
SYMBOLS_PATH = DATA_STORAGE_PATH + "symbols/"
ETF_PATH = SYMBOLS_PATH + "/etf.json"
GENERATED_PATH = CURRENT_FILE_PATH.joinpath("../generated/")
TMP_PATH = CURRENT_FILE_PATH.joinpath("../tmp/")
HISTORY_CACHE_PATH = TMP_PATH.joinpath("history_cache/")
RANGING_STOCKS_PATH = TMP_PATH.joinpath("ranging_stocks/")
ALERTS_PATH = CURRENT_FILE_PATH.joinpath("../live/alert/alert.json")
CACHING_PATH = TMP_PATH.joinpath("caching")
