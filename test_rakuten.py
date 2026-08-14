import unittest
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta, timezone
from rakuten_backtest import run_backtest
from rakuten_trade_plan import calculate_rakuten_trade_plan
from rakuten_market_data import StaleMarketDataError, ensure_fresh_quote


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

    def test_non_supported_rakuten_group_is_not_candidate(self):
        symbols = Path("rakuten_kabumini_symbols.txt").read_text(encoding="utf-8").splitlines()
        self.assertNotIn("4755.T", symbols)

    def test_stale_quote_is_rejected(self):
        old = datetime.now(timezone.utc) - timedelta(days=10)
        data = pd.DataFrame({"Close": [100]}, index=pd.DatetimeIndex([old]))
        with self.assertRaises(StaleMarketDataError):
            ensure_fresh_quote(data)

    def test_backtest_has_risk_metrics(self):
        prices = [100] * 20 + list(range(101, 121)) + list(range(120, 90, -1))
        result = run_backtest(pd.DataFrame({"Close": prices}))
        self.assertIn("max_drawdown", result)
        self.assertIn("win_rate", result)


if __name__ == "__main__":
    unittest.main()
