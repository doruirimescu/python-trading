from datetime import date
import os
from pathlib import Path

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))

DATE_TODAY = str(date.today())
NASDAQ_ANALYSIS_FILENAME = CURRENT_FILE_PATH.joinpath(f"data/nasdaq_analysis_{DATE_TODAY}.json")
EUROPE_ANALYSIS_FILENAME = CURRENT_FILE_PATH.joinpath(f"data/europe_analysis_{DATE_TODAY}.json")
FILTERED_NASDAQ_ANALYSIS_FILENAME = CURRENT_FILE_PATH.joinpath(f"data/nasdaq_analysis_{DATE_TODAY}_filtered.json")
