from Trading.Indicators.indicator_value_to_action import IndicatorAction
from Trading.InvestingAPI.investing_technical import TechnicalAnalysis

class IndicatorActionsToAnalysis:
    def __init__(self, strong=70.0, weak=50.0):
        self.__strong = strong
        self.__weak = weak

    def convert(self, actions):
        n_buy = 0
        n_sell = 0
        for action in actions:
            if action == IndicatorAction.BUY:
                n_buy += 1
            elif action == IndicatorAction.SELL:
                n_sell += 1

        percentage_buy  = n_buy  / (n_buy + n_sell) * 100
        percentage_sell = n_sell / (n_buy + n_sell) * 100

        if percentage_buy > self.__strong:
            return TechnicalAnalysis.STRONG_BUY
        elif percentage_buy > self.__weak:
            return TechnicalAnalysis.BUY
        elif percentage_sell > self.__strong:
            return TechnicalAnalysis.STRONG_SELL
        elif percentage_sell > self.__weak:
            return TechnicalAnalysis.SELL
        elif percentage_buy == percentage_sell:
            return TechnicalAnalysis.NEUTRAL
