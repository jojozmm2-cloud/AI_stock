import unittest

from sbi_watchlist import create_watchlist_embed


class SbiWatchlistTest(unittest.TestCase):
    def test_embed_shows_company_and_distances(self):
        embed = create_watchlist_embed([{
            "code": "2503.T",
            "current_price": 3068.0,
            "take_profit": 3253.5,
            "stop_loss": 2975.25,
            "target_distance": 6.05,
            "stop_distance": -3.02,
            "status": "👀 監視中",
        }])

        self.assertIn("キリン", embed["fields"][0]["name"])
        self.assertIn("+6.05%", embed["fields"][0]["value"])
        self.assertIn("-3.02%", embed["fields"][0]["value"])

    def test_embed_shows_price_error(self):
        embed = create_watchlist_embed([{
            "code": "2503.T",
            "take_profit": 3253.5,
            "stop_loss": 2975.25,
            "error": "現在価格を取得できませんでした",
        }])

        self.assertIn("取得できません", embed["fields"][0]["value"])


if __name__ == "__main__":
    unittest.main()
