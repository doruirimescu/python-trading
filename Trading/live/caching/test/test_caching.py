from unittest import TestCase
from Trading.live.caching.caching import get_caching_dir, get_caching_file_path
from Trading.config.config import CACHING_PATH
from Trading.instrument.instrument import Instrument
from Trading.model.timeframes import Timeframe
from Trading.model.datasource import DataSourceEnum

class TestCaching(TestCase):
    def test_get_caching_dir(self):
        instrument = Instrument("EURUSD", Timeframe("1M"))
        expected = CACHING_PATH.joinpath(DataSourceEnum.XTB.value).joinpath("EURUSD").joinpath("1M")
        self.assertEqual(get_caching_dir(instrument, DataSourceEnum.XTB), expected)

    def test_get_caching_file_path(self):
        instrument = Instrument("EURUSD", Timeframe("1m"))
        expected = get_caching_dir(instrument, DataSourceEnum.XTB).joinpath("data.json")
        self.assertEqual(get_caching_file_path(instrument, DataSourceEnum.XTB), expected)
