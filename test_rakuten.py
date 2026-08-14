import unittest
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta, timezone
from rakuten_backtest import run_backtest, run_one_week_backtest
from rakuten_trade_plan import calculate_rakuten_trade_plan
from rakuten_market_data import StaleMarketDataError, ensure_fresh_quote
from rakuten_short_term import evaluate_short_term_candidate
from rakuten_paper_trade import update_paper_state


class RakutenTests(unittest.TestCase):
    def _paper_candidate(self, market_date, score=80, **overrides):
        item = {"code": "8411.T", "name": "みずほ", "score": score,
                "market_date": market_date, "latest_open": 1000, "latest_high": 1010,
                "latest_low": 990, "latest_close": 1005, "ma20": 980, "atr": 20}
        item.update(overrides)
        return item

    def test_paper_trade_waits_for_next_business_day_open(self):
        state = {"initial_capital": 30000.0, "cash": 30000.0, "pending": None,
                 "position": None, "closed_trades": [], "last_market_date": None}
        state, _ = update_paper_state(state, [self._paper_candidate("2026-08-13")])
        self.assertIsNotNone(state["pending"])
        self.assertIsNone(state["position"])
        state, _ = update_paper_state(state, [self._paper_candidate("2026-08-14")])
        self.assertIsNone(state["pending"])
        self.assertIsNotNone(state["position"])

    def test_paper_trade_does_not_buy_monitor_candidate(self):
        state = {"initial_capital": 30000.0, "cash": 30000.0, "pending": None,
                 "position": None, "closed_trades": [], "last_market_date": None}
        state, events = update_paper_state(state, [self._paper_candidate("2026-08-14", score=64)])
        self.assertIsNone(state["pending"])
        self.assertIn("現金で待機", events[0])

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

    def test_short_term_evaluation_has_separate_evidence(self):
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=1300, freq="B")
        close = pd.Series([100 + index * 0.05 for index in range(len(dates))], index=dates)
        data = pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * .99, "Close": close, "Volume": 1_000_000}, index=dates)
        result = evaluate_short_term_candidate("9432.T", data)
        self.assertEqual(set(result["periods"]), {"1y", "3y", "5y"})
        self.assertIn(result["status"], {"短期候補", "監視候補", "見送り"})

    def test_one_week_strategy_limits_holding_period(self):
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=120, freq="B")
        close = pd.Series([100 + index * .2 for index in range(len(dates))], index=dates)
        data = pd.DataFrame({"Open": close, "High": close * 1.005, "Low": close * .995, "Close": close, "Volume": 1_000_000}, index=dates)
        result = run_one_week_backtest(data)
        self.assertTrue(all(trade["holding_days"] <= 10 for trade in result["trades"]))
        self.assertLessEqual(result["max_drawdown"], 10)

    def test_one_week_strategy_buys_after_signal_day(self):
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=120, freq="B")
        close = pd.Series([100 + index * .15 for index in range(len(dates))], index=dates)
        data = pd.DataFrame({"Open": close * 1.001, "High": close * 1.005, "Low": close * .995, "Close": close, "Volume": 1_000_000}, index=dates)
        result = run_one_week_backtest(data)
        self.assertTrue(result["trades"])
        self.assertTrue(all(trade["entry_date"] > trade["signal_date"] for trade in result["trades"]))


if __name__ == "__main__":
    unittest.main()
