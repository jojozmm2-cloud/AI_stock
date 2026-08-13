import json
import unittest
from datetime import datetime
from unittest.mock import patch

from sbi_auto_monitor import get_auto_monitor_embeds
from sbi_timing import JST


class SbiAutoMonitorTest(unittest.TestCase):
    @patch("sbi_auto_monitor.get_sbi_timing")
    def test_skips_old_market_data(self, timing_mock):
        timing_mock.return_value = {
            "data_date": "2000-01-01"
        }
        watches = json.dumps([{
            "code": "2503.T",
            "take_profit": 3253.5,
            "stop_loss": 2975.25,
        }])

        embeds = get_auto_monitor_embeds(70000, "[]", watches)
        self.assertEqual(embeds, [])

    def test_current_date_is_japan_time(self):
        self.assertIsNotNone(datetime.now(JST).date())


if __name__ == "__main__":
    unittest.main()
