from Trading.utils.time import get_date_now_cet
from Trading.config.config import DATA_STORAGE_PATH
import os
import json
from Trading.utils.custom_logging import get_logger

import json
import os
import signal

LOGGER = get_logger(__file__)


def write_to_json_file(file_name: str, data_dict: dict) -> None:
    f = open(file_name, 'w')
    json_object = json.dumps(data_dict, indent=4, sort_keys=True, default=str)
    f.write(json_object)
    f.close()
    LOGGER.info(f"Wrote to file {file_name}")


def read_json_file(file_name: str) -> dict:
    try:
        with open(file_name, 'r+') as f:
            json_data = json.load(f)
            return json_data
    except Exception as e:
        return None

def extend_json_file(file_name: str, data_dict: dict) -> None:
    try:
        with open(file_name, 'r+') as f:
            json_data = json.load(f)
            json_data.update(data_dict)
            f.seek(0)
            json.dump(json_data, f, indent=4, sort_keys=True, default=str)
    except Exception as e:
        LOGGER.error(f"Error extending file {file_name}: {e}")

def read_historical_data(file_name: str) -> dict:
    ohlc = read_json_file(file_name)
    history = dict()
    history['open'] = list()
    history['high'] = list()
    history['low'] = list()
    history['close'] = list()

    for o, h, l, c in ohlc:
        history['open'].append(o)
        history['high'].append(h)
        history['low'].append(l)
        history['close'].append(c)
    return history


def write_json_to_file_named_with_today_date(json_dict, file_path: str):
    data_path = os.getenv("DATA_STORAGE_PATH", "data/")
    date_today = get_date_now_cet()
    json_path = data_path + file_path + str(date_today) + ".json"
    f = open(json_path, 'w')
    json_object = json.dumps(json_dict, indent=4)
    f.write(json_object)
    f.close()


def read_json_from_file_named_with_today_date(file_path: str):
    date_today = get_date_now_cet()
    json_path = DATA_STORAGE_PATH + file_path + str(date_today) + ".json"
    try:
        with open(json_path, 'r+') as f:
            json_data = json.load(f)
            return json_data
    except Exception as e:
        return None



class JsonFileProcessor:
    def __init__(self, file_name: str):
        self.file_name = file_name
        self.data = self.read_json_file()

        # Setup the signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)

    def read_json_file(self) -> dict:
        """Reads a JSON file and returns its contents as a dictionary."""
        if os.path.exists(self.file_name):
            try:
                with open(self.file_name, 'r') as f:
                    return json.load(f)
            except Exception as e:
                LOGGER.error(f"Error reading file {self.file_name}: {e}")
        return {}

    def write_to_json_file(self) -> None:
        """Writes the current data to a JSON file."""
        try:
            with open(self.file_name, 'w') as f:
                json.dump(self.data, f, indent=4, sort_keys=True, default=str)
            LOGGER.info(f"Wrote to file {self.file_name}")
        except Exception as e:
            LOGGER.error(f"Error writing to file {self.file_name}: {e}")

    def process_data(self):
        """Template method for processing data."""
        # Default implementation: simply pass
        pass

    def signal_handler(self, signum, frame):
        """Handles the SIGINT signal."""
        LOGGER.info("Interrupt signal received, saving data...")
        self.write_to_json_file()
        exit(0)

    def run(self):
        """Main method to run the processor."""
        self.process_data()
        self.write_to_json_file()
