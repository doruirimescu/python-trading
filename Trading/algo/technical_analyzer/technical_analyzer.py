from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis, TrendAnalysis
from Trading.algo.indicators.indicator_value_to_action import IndicatorValueToAction, IndicatorAction
from Trading.algo.indicators.indicator import EMAIndicator

from abc import ABC, abstractmethod
import pandas as pd
import numpy
# import talib


class TechnicalAnalyzer(ABC):
    @abstractmethod
    def analyse(self, *args, **kwargs) -> TechnicalAnalysis:
        pass
