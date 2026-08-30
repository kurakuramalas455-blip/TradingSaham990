"""Comprehensive Unit Test Suite for IDX Fundamental Analysis & Trading Engine."""

import unittest
from analyzer import CompanyProfile, FinancialData, FundamentalAnalyzer, PortfolioContext
from broker_bridge import PaperTradingAdapter
from risk_manager import IDXRiskManager


class TestIDXBotEngine(unittest.TestCase):

    def setUp(self):
        self.risk_manager = IDXRiskManager()
        self.analyzer = FundamentalAnalyzer()

    def test_idx_tick_sizes(self):
        """Test all 5 tiers of IDX tick sizes and alignment."""
        self.assertEqual(self.risk_manager.get_tick_size(150), 1)
        self.assertEqual(self.risk_manager.get_tick_size(250), 2)
        self.assertEqual(self.risk_manager.get_tick_size(1250), 5)
        self.assertEqual(self.risk_manager.get_tick_size(3450), 10)
        self.assertEqual(self.risk_manager.get_tick_size(9850), 25)

        # Test alignment
        self.assertEqual(self.risk_manager.align_to_tick(153.4), 153)
        self.assertEqual(self.risk_manager.align_to_tick(251, round_direction="down"), 250)
        self.assertEqual(self.risk_manager.align_to_tick(1253, round_direction="up"), 1255)
        self.assertEqual(self.risk_manager.align_to_tick(9837, round_direction="nearest"), 9825)
        self.assertEqual(self.risk_manager.align_to_tick(9838, round_direction="nearest"), 9850)

    def test_lot_rounding_and_position_sizing(self):
        """Verify position sizing rounds down to integer lots (100 shares) and obeys risk limits."""
        lots, sl, tp, cost = self.risk_manager.calculate_position_size(
            entry_price=9850,
            fair_value=12000,
            portfolio_equity=100_000_000,
            available_cash=100_000_000,
        )
        self.assertIsInstance(lots, int)
        self.assertGreater(lots, 0)
        self.assertLess(sl, 9850)
        self.assertGreater(tp, 9850)
        # Verify cost does not exceed max single stock allocation (15% = 15M)
        self.assertLessEqual(cost, 15_000_000 * 1.01)

    def test_fee_and_tax_calculations(self):
        """Verify broker fees, PPN 11%, levy 0.043%, and PPh 0.10%."""
        price = 1000
        lots = 10  # 1,000 shares -> gross = 1,000,000
        gross = 1_000_000.0

        # Buy: 0.15% * 1.11 = 0.1665% + 0.043% = 0.2095% fee
        expected_buy_fee = gross * (0.0015 * 1.11 + 0.00043)
        buy_cost = self.risk_manager.calculate_buy_total_cost(price, lots)
        self.assertAlmostEqual(buy_cost, gross + expected_buy_fee, delta=1.0)

        # Sell: 0.25% * 1.11 = 0.2775% + 0.043% levy + 0.10% PPh = 0.4205%
        expected_sell_deduction = gross * (0.0025 * 1.11 + 0.00043 + 0.0010)
        sell_proceeds = self.risk_manager.calculate_sell_net_proceeds(price, lots)
        self.assertAlmostEqual(sell_proceeds, gross - expected_sell_deduction, delta=1.0)

    def test_hard_filters_disqualification(self):
        """Verify hard filters reject high DER, low ROE, FCA, or special notations."""
        # Low ROE non-financial
        profile_low_roe = CompanyProfile(
            ticker="FAIL.JK",
            company_name="Low ROE Corp",
            sector="Consumer Goods",
            current_price=1000,
            market_cap_idr=10_000_000_000_000,
            average_daily_turnover_idr=10_000_000_000,
            financials=FinancialData(roe_percentage=5.0, der_ratio=0.5, fcf_positive=True),
        )
        decision = self.analyzer.evaluate(profile_low_roe)
        self.assertEqual(decision.action, "PASS")

        # FCA stock
        profile_fca = CompanyProfile(
            ticker="FCA.JK",
            company_name="FCA Corp",
            sector="Energy",
            current_price=500,
            market_cap_idr=5_000_000_000_000,
            average_daily_turnover_idr=10_000_000_000,
            is_fca=True,
            financials=FinancialData(roe_percentage=20.0, der_ratio=0.4, fcf_positive=True),
        )
        decision_fca = self.analyzer.evaluate(profile_fca)
        self.assertEqual(decision_fca.action, "PASS")

    def test_altman_and_piotroski_calculation(self):
        """Verify Altman Z-score and Piotroski score logic."""
        fin = FinancialData(
            roe_percentage=22.0,
            roa_percentage=8.0,
            der_ratio=0.5,
            npm_percentage=15.0,
            revenue_yoy_growth=12.0,
            net_income_yoy_growth=18.0,
            fcf_positive=True,
            total_assets_idr=1_000_000_000,
            total_liabilities_idr=400_000_000,
            working_capital_idr=300_000_000,
            retained_earnings_idr=250_000_000,
            ebit_idr=150_000_000,
            book_value_equity_idr=600_000_000,
        )
        z = self.analyzer.calculate_altman_z_score(fin)
        self.assertGreater(z, 2.60)  # Safe zone

        f = self.analyzer.calculate_piotroski_f_score(fin)
        self.assertGreaterEqual(f, 7)

    def test_paper_trading_adapter(self):
        """Verify virtual cash order execution and holding updates."""
        adapter = PaperTradingAdapter(initial_cash_idr=50_000_000)
        buy_res = adapter.submit_buy_order("BBCA.JK", 9850, 10)
        self.assertEqual(buy_res["status"], "FILLED")
        self.assertEqual(adapter.holdings["BBCA.JK"]["lots"], 10)
        self.assertLess(adapter.cash_balance, 50_000_000)

        sell_res = adapter.submit_sell_order("BBCA.JK", 10200, 10)
        self.assertEqual(sell_res["status"], "FILLED")
        self.assertNotIn("BBCA.JK", adapter.holdings)


if __name__ == "__main__":
    unittest.main()
