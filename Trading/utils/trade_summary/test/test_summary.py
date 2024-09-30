from unittest import TestCase
from Trading.model.trade import Trade, BuyTrade
from Trading.utils.trade_summary.summary import (
    get_start_date,
    get_end_date,
    get_invested_money,
)


class TestSummary(TestCase):
    def test_get_start_date(self):
        test_trades = [
            BuyTrade(entry_date="2021-01-01", exit_date="2021-01-02"),
            BuyTrade(entry_date="2021-01-03", exit_date="2021-01-04"),
            BuyTrade(entry_date="2021-01-05", exit_date="2021-01-06"),
        ]
        self.assertEqual(get_start_date(test_trades), "2021-01-01")

    def test_get_end_date(self):
        test_trades = [
            BuyTrade(entry_date="2021-01-01", exit_date="2021-01-02"),
            BuyTrade(entry_date="2021-01-03", exit_date="2021-01-04"),
            BuyTrade(entry_date="2021-01-05", exit_date="2021-01-06"),
        ]
        self.assertEqual(get_end_date(test_trades), "2021-01-06")

    def test_get_invested_money(self):
        # Empty list
        test_trades = []
        self.assertEqual(get_invested_money(test_trades), 0)

        # Single trade with same entry and exit date
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-01",
                volume=1,
                open_price=10,
                close_price=12,
                profit=2,
            ),
        ]
        self.assertEqual(get_invested_money(test_trades), 10)

        # One trade, no reinvestment
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-02",
                volume=1,
                open_price=1.5,
                close_price=2,
                profit=1,
            ),
        ]
        self.assertEqual(get_invested_money(test_trades), 1.5)

        # Two trades, no reinvestment
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-03",
                volume=1,
                open_price=1,
                close_price=2,
                profit=1,
            ),
            BuyTrade(
                entry_date="2021-01-02",
                exit_date="2021-01-03",
                volume=1,
                open_price=2,
                close_price=3,
                profit=1,
            ),
        ]
        self.assertEqual(get_invested_money(test_trades), 3)

        # Two trades, reinvestment, first trade on win
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-03",
                volume=1,
                open_price=1,
                close_price=6,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-05",
                exit_date="2021-01-06",
                volume=1,
                open_price=7,
                close_price=7,
                profit=0,
            ),
        ]
        self.assertEqual(get_invested_money(test_trades), 2)

        # Two trades, reinvestment, first trade on loss
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-03",
                volume=1,
                open_price=5,
                close_price=2,
                profit=-3,
            ),
            BuyTrade(
                entry_date="2021-01-05",
                exit_date="2021-01-06",
                volume=1,
                open_price=7,
                close_price=3,
                profit=1,
            ),
        ]
        self.assertEqual(get_invested_money(test_trades), 10)

        # Three trades, reinvestment, all trades on win, entry and exit date are the same
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-01",
                volume=1,
                open_price=10,
                close_price=12,
                profit=2,
            ),
            BuyTrade(
                entry_date="2021-01-02",
                exit_date="2021-01-02",
                volume=1,
                open_price=20,
                close_price=25,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-03",
                exit_date="2021-01-03",
                volume=1,
                open_price=30,
                close_price=35,
                profit=5,
            ),
        ]
        self.assertEqual(get_invested_money(test_trades), 23)

        # Completely reinvested trades
        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-02",
                volume=1,
                open_price=10,
                close_price=15,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-03",
                exit_date="2021-01-04",
                volume=1,
                open_price=5,
                close_price=10,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-05",
                exit_date="2021-01-06",
                volume=1,
                open_price=10,
                close_price=12,
                profit=2,
            ),
        ]
        self.assertEqual(
            get_invested_money(test_trades), 10
        )  # Only initial input for the first trade required

        test_trades = [
            BuyTrade(
                entry_date="2021-01-01",
                exit_date="2021-01-10",
                volume=1,
                open_price=10,
                close_price=15,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-05",
                exit_date="2021-01-06",
                volume=1,
                open_price=20,
                close_price=25,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-07",
                exit_date="2021-01-12",
                volume=1,
                open_price=30,
                close_price=35,
                profit=5,
            ),
            BuyTrade(
                entry_date="2021-01-11",
                exit_date="2021-01-15",
                volume=1,
                open_price=40,
                close_price=30,
                profit=-10,
            ),
        ]
        self.assertEqual(
            get_invested_money(test_trades), 50
        )  # Analyzes input money needed considering reinvestments
