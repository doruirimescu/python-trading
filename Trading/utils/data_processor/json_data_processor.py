from abc import abstractmethod
from Trading.utils.custom_logging import get_logger
import json
import signal
import os
from typing import Optional

LOGGER = get_logger(__file__)

'''
    Process large amounts of data in a JSON file incrementally.
    The data is stored in a dictionary and the processor keeps track of the current step being processed.
    The processor can be interrupted with a SIGINT signal and the data will be saved to the file.
    The processor is meant to be subclassed and the _process_data method should be implemented.
    The process_item method should be implemented to process a single item, if iterate_items is used.
'''
class JsonFileRW:
    def __init__(self, file_name: str, should_read: Optional[bool] = True):
        self.file_name = file_name
        if should_read:
            self.data = self.read()
        else:
            self.data = {}

    def read(self) -> dict:
        """Reads a JSON file and returns its contents as a dictionary."""
        if not os.path.exists(self.file_name):
            LOGGER.info(f"File {self.file_name} does not exist.")
            return {}
        try:
            with open(self.file_name, "r") as f:
                return json.load(f)
        except Exception as e:
            LOGGER.error(f"Error reading file {self.file_name}: {e}")
            raise e


    def write(self) -> None:
        """Writes the current data to a JSON file."""
        try:
            with open(self.file_name, "w") as f:
                json.dump(self.data, f, indent=4, sort_keys=True, default=str)
            LOGGER.info(f"Wrote to file {self.file_name}")
        except Exception as e:
            LOGGER.error(f"Error writing to file {self.file_name}: {e}")
            raise e

class JsonDataProcessor(JsonFileRW):  #! Replace inheritance with composition
    def __init__(self, file_name: str, should_read: Optional[bool] = True):
        super().__init__(file_name, should_read)
        LOGGER.info(f"reading from file: {file_name} data of len {len(self.data)}")
        # Incremental counter to keep track of the current step being processed

        # Setup the signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)


    @abstractmethod
    def _process_data(self, *args, **kwargs):
        """Template method for processing data."""
        ...

    def iterate_items(self, items, *args, **kwargs):
        """General iteration method for processing items."""
        items_len = len(items)
        for step, item in enumerate(items):
            if item in self.data:
                LOGGER.info(f"Item {item} already processed, skipping...")
                continue
            try:
                self.process_item(item, *args, **kwargs)
            except Exception as e:
                LOGGER.error(f"Error processing item {item}: {e}")
                self.write()
            LOGGER.info(f"Processed item {item} {len(self.data)} / {items_len}")
        LOGGER.info("Finished processing all items.")

    @abstractmethod
    def process_item(self, item, *args, **kwargs):
        """Process a single item."""
        pass

    def _signal_handler(self, signum, frame):
        """Handles the SIGINT signal."""
        LOGGER.info("Interrupt signal received, saving data...")
        self.write()
        LOGGER.info("Data saved, exiting.")
        exit(0)

    def run(self, *args, **kwargs):
        """Main method to run the processor."""
        self._process_data(*args, **kwargs)
        self.write()
