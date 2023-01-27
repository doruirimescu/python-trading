from dataclasses import dataclass
from Trading.Instrument.symbol_investing_to_x import SYMBOL_XTB_INDEX, SYMBOL_INVESTING_INDEX, SYMBOL_TO_X


@dataclass
class Instrument:
    '''
        Symbol expressed as xtb
    '''
    symbol: str
    timeframe: str

    def getSymbolXTB(self):
        # return SYMBOL_TO_X[self.symbol][SYMBOL_XTB_INDEX]
        return self.symbol

    def getSymbolInvesting(self):
        return SYMBOL_TO_X[self.symbol][SYMBOL_INVESTING_INDEX]
