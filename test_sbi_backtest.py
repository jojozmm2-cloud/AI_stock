import unittest

import pandas as pd

from sbi_backtest import Position, close_position, relative_signal


class SbiBacktestTest(unittest.TestCase):
    def test_capital_string_is_accepted_by_public_runner_signature(self):
        self.assertEqual(int(float("100000")), 100000)

    def test_same_day_target_and_stop_uses_stop(self):
        position = Position("TEST", "momentum", 2, 100, 95, 110, 0, 200)
        result = close_position(
            position,
            pd.Series({"High": 110, "Low": 90, "Close": 105}),
            day_index=1,
            params={"holding": 10},
        )
        self.assertEqual(result, (95, "loss"))

    def test_target_is_taxed(self):
        position = Position("TEST", "momentum", 2, 100, 95, 110, 0, 200)
        result = close_position(
            position,
            pd.Series({"High": 111, "Low": 99, "Close": 110}),
            day_index=1,
            params={"holding": 10},
        )
        self.assertEqual(result, (110, "win"))

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
