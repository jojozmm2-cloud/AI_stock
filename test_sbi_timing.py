import unittest
from datetime import datetime

from sbi_timing import (
    JST,
    decide_buy,
    decide_sell,
    make_action_comment,
    make_sparkline,
    next_sbi_window,
)


class SbiTimingTest(unittest.TestCase):
    def test_buy_waits_when_overheated(self):
        decision, _ = decide_buy(102, 100, 72, 0.5, 101, 99)
        self.assertIn("待つ", decision)

    def test_buy_considers_aligned_trend(self):
        decision, _ = decide_buy(101, 100, 55, 0.3, 101, 99)
        self.assertIn("検討", decision)

    def test_sell_detects_take_profit(self):
        decision, _ = decide_sell(110, 105, 0.2, 109, 95)
        self.assertIn("利確", decision)

    def test_sbi_window_before_morning_deadline(self):
        now = datetime(2026, 8, 12, 10, 0, tzinfo=JST)
        deadline, execution = next_sbi_window(now)
        self.assertIn("10:30", deadline)
        self.assertIn("12:30", execution)

    def test_sparkline_has_same_length(self):
        self.assertEqual(len(make_sparkline([1, 2, 3, 2])), 4)

    def test_buy_comment_recommends_recheck_after_close(self):
        comment = make_action_comment({
            "action": "buy",
            "decision": "🟢 次の注文枠で検討",
            "shares": 7,
            "market_open": False,
        })
        self.assertIn("翌営業日", comment)
        self.assertIn("もう一度", comment)


if __name__ == "__main__":
    unittest.main()
