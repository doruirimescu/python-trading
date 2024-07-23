from dataclasses import dataclass
from Trading.model.timeframes import Timeframe

@dataclass
class Instrument:
    '''
        Symbol expressed as xtb
    '''
    symbol: str
    timeframe: Timeframe

    def get_symbol_xtb(self):
        # return SYMBOL_TO_X[self.symbol][SYMBOL_XTB_INDEX]
        return self.symbol
