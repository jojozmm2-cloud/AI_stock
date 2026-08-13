import unittest

import pandas as pd

from sbi_candidates import score_candidate


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
        self.assertGreater(result["expected_net_profit"], result["max_loss"])

    def test_overheated_stock_is_excluded(self):
        data = self.make_data()
        data["Close"] = [900 + 15 * index for index in range(30)]
        data["High"] = data["Close"] + 12
        data["Low"] = data["Close"] - 12
        result = score_candidate(data, capital=70_000)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
