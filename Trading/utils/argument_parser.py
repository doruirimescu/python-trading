import argparse
from Trading.instrument.instrument import Instrument
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
    return Instrument(args.symbol, args.timeframe)


class CustomParser:
    def __init__(self) -> None:
        self.description = "Enter"
        self.parser: Optional[argparse.ArgumentParser] = None
        self.config: List[Tuple[str, str, type]] = list()
        self.expressions: List[str] = list()

    def add_instrument(self):
        self.description += "currency, timeframe"
        self.config.append(('-s', 'symbol', str))
        self.config.append(('-t', 'timeframe', str))
        self.expressions.append('symbol')
        self.expressions.append('timeframe')

    def add_contract_value(self):
        self.description += ",contract_value"
        self.config.append(('-cv', 'contract_value', int))
        self.expressions.append('contract_value')

    def add_xtb_mode(self):
        self.description += ", xtb_mode"
        self.config.append(('-xtbm', 'xtb_mode', str))
        self.expressions.append('xtb_mode')

    def add_xtb_username(self):
        self.description += ", xtb_username"
        self.config.append(('-xtbu', 'xtb_username', str))
        self.expressions.append('xtb_username')

    def add_xtb_password(self):
        self.description += ", xtb_password"
        self.config.append(('-xtbp', 'xtb_password', str))
        self.expressions.append('xtb_password')

    def build(self):
        self.parser = argparse.ArgumentParser(description=self.description)
        for f, d, t in self.config:
            self.parser.add_argument(f, dest=d, type=t, required=True)

    def parse_args(self) -> List:
        self.build()
        args = self.parser.parse_args()
        values = list()
        for expr in self.expressions:
            value = eval('args.' + expr)
            values.append(value)
        return values
