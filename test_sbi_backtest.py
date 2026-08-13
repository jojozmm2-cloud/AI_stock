import unittest

import pandas as pd

from sbi_backtest import evaluate_trade


class SbiBacktestTest(unittest.TestCase):
    def test_same_day_target_and_stop_uses_stop(self):
        future = pd.DataFrame({"High": [110], "Low": [90], "Close": [105]})
        result = evaluate_trade(future, entry_price=100, risk_per_share=5, shares=2)
        self.assertEqual(result["outcome"], "loss")
        self.assertEqual(result["pnl"], -10)

    def test_target_is_taxed(self):
        future = pd.DataFrame({"High": [111], "Low": [99], "Close": [110]})
        result = evaluate_trade(future, entry_price=100, risk_per_share=5, shares=2)
        self.assertEqual(result["outcome"], "win")
        self.assertGreater(result["pnl"], 15)
        self.assertLess(result["pnl"], 20)


if __name__ == "__main__":
    unittest.main()
