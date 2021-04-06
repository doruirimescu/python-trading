from Trading.Live.Logger.logger import DataLogger

# 11989223
with DataLogger('EURUSD', '30m', "data/", 100) as data_logger:
    print("Started logging")
    data_logger.mainLoop()
