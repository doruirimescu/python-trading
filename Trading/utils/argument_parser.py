import argparse
from Trading.instrument.instrument import Instrument


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
