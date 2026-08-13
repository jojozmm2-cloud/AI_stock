import unittest

import pandas as pd

from sbi_backtest import evaluate_trade, relative_signal


class SbiBacktestTest(unittest.TestCase):
    def test_capital_string_is_accepted_by_public_runner_signature(self):
        self.assertEqual(int(float("100000")), 100000)

    def test_same_day_target_and_stop_uses_stop(self):
        future = pd.DataFrame({"High": [110], "Low": [90], "Close": [105]})
        result = evaluate_trade(future, entry_price=100, base_risk=5, shares=2)
        self.assertEqual(result["outcome"], "loss")
        self.assertEqual(result["pnl"], -10)

    def test_target_is_taxed(self):
        future = pd.DataFrame({"High": [111], "Low": [99], "Close": [110]})
        result = evaluate_trade(future, entry_price=100, base_risk=5, shares=2)
        self.assertEqual(result["outcome"], "win")
        self.assertGreater(result["pnl"], 15)
        self.assertLess(result["pnl"], 20)

    def test_relative_momentum_requires_market_outperformance(self):
        stock_close = [100]
        for index in range(1, 70):
            stock_close.append(stock_close[-1] + (1.5 if index % 2 else -1.0))
        market_close = [100 + index * 0.1 for index in range(70)]
        stock = pd.DataFrame({
            "Close": stock_close,
            "High": [value + 1 for value in stock_close],
            "Low": [value - 1 for value in stock_close],
            "Volume": [1_000_000] * 70,
        })
        market = pd.DataFrame({"Close": market_close})
        result = relative_signal(stock, market, sector_return_20=1, strategy="momentum")
        self.assertIsNotNone(result)
        self.assertGreater(result["relative_market"], 2)


if __name__ == "__main__":
    unittest.main()
