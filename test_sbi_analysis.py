import unittest

from sbi_analysis import calculate_trade_plan, create_sbi_analysis_embed


class SbiAnalysisTest(unittest.TestCase):
    def test_position_is_limited_by_risk(self):
        plan = calculate_trade_plan(
            capital=70000,
            current_price=1000,
            atr=25
        )

        self.assertEqual(plan["shares"], 28)
        self.assertEqual(plan["max_loss"], 700)
        self.assertEqual(plan["take_profit"], 1050)
        self.assertEqual(plan["stop_loss"], 975)
        self.assertEqual(plan["gross_profit"], 1400)
        self.assertAlmostEqual(plan["estimated_tax"], 284.41)
        self.assertAlmostEqual(plan["net_profit"], 1115.59)
        self.assertAlmostEqual(
            plan["after_tax_reward_ratio"],
            1.5937
        )

    def test_position_is_limited_by_capital(self):
        plan = calculate_trade_plan(
            capital=70000,
            current_price=30000,
            atr=100
        )

        self.assertEqual(plan["shares"], 1)
        self.assertEqual(plan["investment"], 30000)

    def test_unaffordable_risk_is_a_skip(self):
        plan = calculate_trade_plan(
            capital=70000,
            current_price=50000,
            atr=1200
        )
        plan["code"] = "9999.T"
        embed = create_sbi_analysis_embed(plan)

        self.assertEqual(plan["shares"], 0)
        self.assertIn("見送り", embed["description"])


if __name__ == "__main__":
    unittest.main()
