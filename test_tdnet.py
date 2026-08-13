import unittest
from datetime import date

from tdnet import (
    analyze_disclosure_document, classify_disclosure, create_tdnet_test_embed,
    parse_tdnet_html, summarize_tdnet,
)


class TdnetTest(unittest.TestCase):
    def test_parse_official_row(self):
        html = '''<table><tr>
        <td class="kjTime">15:30</td><td class="kjCode">12340</td>
        <td class="kjName">テスト株式会社</td>
        <td class="kjTitle"><a href="140120260814000001.pdf">業績予想の上方修正</a></td>
        </tr></table>'''
        result = parse_tdnet_html(html, date(2026, 8, 14))
        self.assertEqual(result[0]["code"], "1234")
        self.assertIn("上方修正", result[0]["title"])
        self.assertEqual(
            result[0]["url"],
            "https://www.release.tdnet.info/inbs/140120260814000001.pdf",
        )

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

    def test_sponsorship_and_buyback_completion_are_neutral(self):
        self.assertEqual(classify_disclosure("学生向け就職支援サービスのスポンサー契約"), "neutral")
        self.assertEqual(classify_disclosure("自己株式の取得状況及び取得終了"), "neutral")

    def test_partnership_requires_concrete_impact(self):
        item = {"title": "株式会社Bとの業務提携に関するお知らせ"}
        neutral = analyze_disclosure_document(item, "本件による業績への影響は軽微です。")
        self.assertEqual(neutral["sentiment"], "neutral")
        positive = analyze_disclosure_document(item, "本提携に伴い業績予想を上方修正します。")
        self.assertEqual(positive["sentiment"], "positive")


if __name__ == "__main__":
    unittest.main()
