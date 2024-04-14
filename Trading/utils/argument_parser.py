import argparse
from Trading.instrument import Instrument, Timeframe
from typing import List, Tuple, Optional


def get_instrument():
    """Creates an instrument object from the command line arguments.

    Returns:
        instrument: instrument for which the logging is performed.
    """
    parser = argparse.ArgumentParser(description='Enter currency and timeframe.')
    parser.add_argument('-s', dest='symbol', type=str, required=True)
    parser.add_argument('-t', dest='timeframe', type=str, required=True)
    args = parser.parse_args()
    return Instrument(args.symbol, Timeframe(args.timeframe))


class CustomParser:
    """Custom argument parser which allows you to generate arguments in a reusable manner
    """
    def __init__(self, description ="") -> None:
        self.__description = description
        self.__parser: Optional[argparse.ArgumentParser] = None
        self.__config: List[Tuple[str, str, type]] = list()
        self.__expressions: List[str] = list()

    def add_instrument(self):
        """-s symbol -t timeframe
        """
        self.__description += "currency, timeframe"
        self.__config.append(('-s', 'symbol', str))
        self.__config.append(('-t', 'timeframe', str))
        self.__expressions.append('symbol')
        self.__expressions.append('timeframe')

    def add_contract_value(self):
        """-cv contract_value
        """
        self.__description += ",contract_value"
        self.__config.append(('-cv', 'contract_value', int))
        self.__expressions.append('contract_value')

    def add_xtb_mode(self):
        """-xtbm demo/real
        """
        self.__description += ", xtb_mode"
        self.__config.append(('-xtbm', 'xtb_mode', str))
        self.__expressions.append('xtb_mode')

    def add_xtb_username(self):
        """-xtbu username
        """
        self.__description += ", xtb_username"
        self.__config.append(('-xtbu', 'xtb_username', str))
        self.__expressions.append('xtb_username')

    def add_xtb_password(self):
        """-xtbp password
        """
        self.__description += ", xtb_password"
        self.__config.append(('-xtbp', 'xtb_password', str))
        self.__expressions.append('xtb_password')

    def build(self):
        self.__parser = argparse.ArgumentParser(description=self.__description)
        for f, d, t in self.__config:
            self.__parser.add_argument(f, dest=d, type=t, required=True)

    def parse_args(self) -> List:
        self.build()
        args = self.__parser.parse_args()
        values = list()
        for expr in self.__expressions:
            value = eval('args.' + expr)
            values.append(value)
        return values
