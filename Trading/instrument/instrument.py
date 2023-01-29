from dataclasses import dataclass
from Trading.instrument.symbol_investing_to_x import SYMBOL_XTB_INDEX, SYMBOL_INVESTING_INDEX, SYMBOL_TO_X


@dataclass
class Instrument:
    '''
        Symbol expressed as xtb
    '''
    symbol: str
    timeframe: str

    def get_symbol_xtb(self):
        # return SYMBOL_TO_X[self.symbol][SYMBOL_XTB_INDEX]
        return self.symbol

    def get_symbol_investing(self):
        return SYMBOL_TO_X[self.symbol][SYMBOL_INVESTING_INDEX]
