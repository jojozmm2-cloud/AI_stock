import unittest
from datetime import date

from tdnet import classify_disclosure, create_tdnet_test_embed, parse_tdnet_html, summarize_tdnet


class TdnetTest(unittest.TestCase):
    def test_parse_official_row(self):
        html = '''<table><tr>
        <td class="kjTime">15:30</td><td class="kjCode">12340</td>
        <td class="kjName">テスト株式会社</td>
        <td class="kjTitle"><a href="./140120260814000001.pdf">業績予想の上方修正</a></td>
        </tr></table>'''
        result = parse_tdnet_html(html, date(2026, 8, 14))
        self.assertEqual(result[0]["code"], "1234")
        self.assertIn("上方修正", result[0]["title"])
        self.assertTrue(result[0]["url"].startswith("https://"))

    def test_negative_takes_priority(self):
        self.assertEqual(classify_disclosure("業績予想の下方修正及び減配"), "negative")
        summary = summarize_tdnet([{
            "date": date(2026, 8, 14), "time": "15:00", "title": "減配",
            "sentiment": "negative", "url": "", "code": "1234", "company": "A",
        }])
        self.assertTrue(summary["negative"])

    def test_test_embed_handles_no_disclosures(self):
        embed = create_tdnet_test_embed({})
        self.assertIn("0件", embed["description"])
        self.assertEqual(embed["fields"][0]["value"], "該当なし")


if __name__ == "__main__":
    unittest.main()
