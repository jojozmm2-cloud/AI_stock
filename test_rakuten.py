import unittest
import pandas as pd
from rakuten_backtest import run_backtest
from rakuten_trade_plan import calculate_rakuten_trade_plan


class RakutenTests(unittest.TestCase):
    def test_plan_never_exceeds_capital(self):
        plan = calculate_rakuten_trade_plan(1000, 30, capital=30_000)
        self.assertLessEqual(plan["investment"], 30_000)

    def test_spread_reduces_profit(self):
        self.assertLess(calculate_rakuten_trade_plan(1000, 30, spread_rate=.0022)["net_profit"], calculate_rakuten_trade_plan(1000, 30, spread_rate=0)["net_profit"])

    def test_backtest_returns_summary(self):
        prices = [100] * 20 + list(range(101, 121)) + list(range(120, 90, -1))
        result = run_backtest(pd.DataFrame({"Close": prices}))
        self.assertIn("final_value", result)
        self.assertGreaterEqual(result["trade_count"], 1)


if __name__ == "__main__":
    unittest.main()
