import unittest
from datetime import date

import pandas as pd

from sbi_candidates import evaluate_market_data, in_earnings_blackout, score_candidate


class SbiCandidatesTest(unittest.TestCase):
    def make_data(self, start=950, volume=1_000_000):
        pattern = [0, 4, -2, 3, -1]
        close = [start + index + pattern[index % len(pattern)] for index in range(30)]
        return pd.DataFrame({
            "Close": close,
            "High": [value + 12 for value in close],
            "Low": [value - 12 for value in close],
            "Volume": [volume] * 29 + [volume * 1.3],
        })

    def test_candidate_contains_s_stock_profit_plan(self):
        result = score_candidate(self.make_data(), capital=70_000)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["shares"], 1)
        self.assertGreater(result["take_profit"], result["price"])
        self.assertLess(result["stop_loss"], result["price"])
        self.assertGreater(result["take_profit_net_profit"], result["planned_loss"])
        self.assertEqual(result["stress_loss_2x"], result["planned_loss"] * 2)

    def test_overheated_stock_is_excluded(self):
        data = self.make_data()
        data["Close"] = [900 + 15 * index for index in range(30)]
        data["High"] = data["Close"] + 12
        data["Low"] = data["Close"] - 12
        result = score_candidate(data, capital=70_000)
        self.assertIsNone(result)

    def test_market_data_detects_weak_market(self):
        close = [100 + index for index in range(20)] + [90]
        result = evaluate_market_data(pd.DataFrame({"Close": close}))
        self.assertTrue(result["weak"])
        self.assertTrue(result["sharp_drop"])

    def test_earnings_blackout_uses_business_days(self):
        earnings = date(2026, 8, 14)
        self.assertTrue(in_earnings_blackout(earnings, date(2026, 8, 11)))
        self.assertTrue(in_earnings_blackout(earnings, date(2026, 8, 17)))
        self.assertFalse(in_earnings_blackout(earnings, date(2026, 8, 10)))
        self.assertFalse(in_earnings_blackout(earnings, date(2026, 8, 18)))


if __name__ == "__main__":
    unittest.main()
