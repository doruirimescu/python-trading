from Trading.live.client.client import XTBTradingClient
from Trading.utils.time import get_date_now_cet
from Trading.algo.technical_analyzer.technical_analyzer import DailyBuyTechnicalAnalyzer
from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from Trading.algo.trade.trade import TradeType, Trade
from Trading.instrument.instrument import Instrument
from Trading.utils.write_to_file import write_json_to_file_named_with_today_date, read_json_from_file_named_with_today_date
from datetime import date
from typing import Dict

from dotenv import load_dotenv
import os
import logging
import time

trades_dict = read_json_from_file_named_with_today_date('trades/')
print(trades_dict)
if trades_dict is None:
    trades_dict = dict()
if __name__ == '__main__':
    date_now_cet = str(get_date_now_cet())
    contract_value = 1000
    t = Trade(date_=date_now_cet, type_=TradeType.BUY, contract_value=contract_value)

    trades_dict[date_now_cet] = t.get_dict()
    write_json_to_file_named_with_today_date(trades_dict, 'trades/')
