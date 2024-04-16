from abc import abstractmethod
from logging import Logger
from typing import Dict
import os
import json

class FileRW:
    def __init__(self, file_name: str, logger: Logger) -> None:
        self.file_name = file_name
        self.logger = logger

    @abstractmethod
    def read(self) -> Dict:
        ...

    @abstractmethod
    def write(self, data) -> None:
        ...

class JsonFileRW(FileRW):
    def __init__(self, file_name: str, logger: Logger):
        super().__init__(file_name, logger)

    def read(self) -> Dict:
        """Reads a JSON file and returns its contents as a dictionary."""
        if not os.path.exists(self.file_name):
            self.logger.info(f"File {self.file_name} does not exist.")
            return {}
        try:
            with open(self.file_name, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading file {self.file_name}: {e}")
            raise e

    def write(self, data: Dict) -> None:
        """Writes the current data to a file."""
        try:
            with open(self.file_name, "w") as f:
                json.dump(data, f, indent=4, sort_keys=True, default=str)
            self.logger.info(f"Wrote to file {self.file_name}")
        except Exception as e:
            self.logger.error(f"Error writing to file {self.file_name}: {e}")
            raise e
