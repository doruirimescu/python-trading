import pandas as pd
from Trading.algo.technical_analyzer.technical_analysis import TrendAnalysis
from typing import Tuple


class BollingerBandsIndicator:
    def __init__(self, window: int = 20, num_std: int = 2) -> None:
        self.window = window
        self.num_std = num_std
        self.data = None

    def calculate_bb(self, df: pd.DataFrame, ohlc='close') -> Tuple[float, float]:
        rolling_mean = df[ohlc].rolling(window=self.window).mean()
        rolling_std = df[ohlc].rolling(window=self.window).std()
        upper_band = rolling_mean + (rolling_std * self.num_std)
        lower_band = rolling_mean - (rolling_std * self.num_std)
        df['rolling_mean'] = rolling_mean
        df['upper_band'] = upper_band
        df['lower_band'] = lower_band
        self.data = df
        return lower_band.iloc[-1], upper_band.iloc[-1]

    def plot(self, ax):
        ax.plot(self.data.rolling_mean, label=f'Rolling mean{self.window}', color='blue')
        ax.plot(self.data.upper_band, label=f'Upper band', color='red')
        ax.plot(self.data.lower_band, label=f'Lower band', color='green')
        ax.legend()


def moving_average(df, window=20, open_close='close'):
    df['moving_avg'] = df[open_close].rolling(window=window).mean()


class EMAIndicator:
    def __init__(self, window=20):
        self.window = window
        self.data = None
        self.ema = None

    def calculate_ema(self, data: pd.DataFrame, ohlc='open'):
        self.data = data
        self.ema = self.data[ohlc].ewm(span=self.window, adjust=False).mean()
        return self.ema.iloc[-1]

    def plot(self, ax, color='orange'):
        ax.plot(self.ema, label=f'EMA{self.window}', color=color)
        ax.legend()

    def get_trend(self, n: int = 30):
        total_up = 0
        total_down = 0
        #Check low trend
        for p, e in zip(self.data['high'][-n:], self.ema[-n:]):
            if p < e:
                total_down += 1

        for p, e in zip(self.data['low'][-n:], self.ema[-n:]):
            if p > e:
                total_up += 1
        result = TrendAnalysis.SIDE
        if total_up / n > 0.9:
            result = TrendAnalysis.UP
        elif total_down / n > 0.9:
            result = TrendAnalysis.DOWN
        return result