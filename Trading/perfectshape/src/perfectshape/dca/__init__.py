"""perfectshape.dca: can a monthly saver beat plain dollar-cost averaging into the S&P 500 by choosing *when*
each payment goes in?

The saver gets a fixed amount every month. The benchmark invests it the day it arrives. The strategy may hold a
payment back (up to six of them) or borrow coming payments on margin and invest them now (up to six), and never
sells. ``data`` loads the market history, ``account`` simulates the account (interest, margin rules, many start
dates at once), ``signals`` and ``policy`` turn market data into "how many payments ahead or behind to be",
``evaluate`` compares against the benchmark over every start date. See README, "DCA".
"""
