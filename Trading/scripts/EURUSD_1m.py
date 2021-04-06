from Trading.Live.Logger.logger import DataLogger

# 11989223
with DataLogger('EURUSD', '1m', "data/", 20) as data_logger:
    print("Started logging")
    data_logger.mainLoop()
