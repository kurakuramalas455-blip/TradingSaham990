"""Workflow Orchestrator for IDX Fundamental Analysis & Trading Bot Engine."""

import json
from typing import Any, Dict, List
from analyzer import CompanyProfile, DecisionOutput, FinancialData, FundamentalAnalyzer, PortfolioContext
from broker_bridge import HeadlessWebAdapter, PaperTradingAdapter, TelegramAlertAdapter
from config import settings
from risk_manager import IDXRiskManager


class IDXTradingBot:
    """End-to-end bot engine for screening, scoring, risk management, and order dispatch."""

    def __init__(self):
        self.analyzer = FundamentalAnalyzer()
        self.risk_manager = IDXRiskManager()
        self.paper_broker = PaperTradingAdapter()
        self.web_broker = HeadlessWebAdapter()

    def process_stock(self, profile: CompanyProfile) -> Dict[str, Any]:
        """Evaluates a single company profile, applies position sizing, and prepares order payload."""
        # 1. Fundamental evaluation & decision matrix
        decision: DecisionOutput = self.analyzer.evaluate(profile)

        # 2. Risk Management & Position Sizing (if BUY or active)
        portfolio_status = self.paper_broker.get_portfolio_status()
        available_cash = portfolio_status["cash_balance_idr"]
        portfolio_equity = available_cash + sum(
            h["lots"] * 100 * h["avg_price"] for h in portfolio_status["holdings"].values()
        )

        lots = 0
        sl_price = 0
        tp_price = int(decision.valuation_summary.fair_value_estimate)
        est_cost = 0.0

        if decision.action == "BUY":
            lots, sl_price, tp_price, est_cost = self.risk_manager.calculate_position_size(
                entry_price=profile.current_price,
                fair_value=decision.valuation_summary.fair_value_estimate,
                portfolio_equity=portfolio_equity,
                available_cash=available_cash,
            )
            # If position size is 0 due to cash/risk limits, downgrade to WATCHLIST
            if lots == 0:
                decision.action = "WATCHLIST"
                decision.analysis_rationale.append(
                    "Sinyal beli valid namun alokasi lot = 0 karena batasan risiko atau cash buffer minimum."
                )

        elif decision.action == "SELL":
            current_holding = profile.financials.current_holding_lots
            lots = current_holding
            sl_price = int(profile.current_price * 0.95)

        # Update execution details
        decision.execution_details.target_price = profile.current_price
        decision.execution_details.calculated_lots = lots
        decision.execution_details.estimated_cost_idr = est_cost
        decision.execution_details.stop_loss_price = sl_price
        decision.execution_details.take_profit_price = tp_price

        # 3. Execution Dispatch
        payload = decision.model_dump()

        if decision.action == "BUY" and lots > 0:
            if settings.DRY_RUN or not settings.ENABLE_LIVE_TRADING:
                self.paper_broker.submit_buy_order(profile.ticker, int(profile.current_price), lots)
            else:
                self.web_broker.submit_buy_order(profile.ticker, int(profile.current_price), lots)

        elif decision.action == "SELL" and lots > 0:
            if settings.DRY_RUN or not settings.ENABLE_LIVE_TRADING:
                self.paper_broker.submit_sell_order(profile.ticker, int(profile.current_price), lots)
            else:
                self.web_broker.submit_sell_order(profile.ticker, int(profile.current_price), lots)

        return payload


def run_sample_pipeline():
    """Demonstrates screening & evaluation of sample IDX tickers (e.g. BBCA.JK, BBRI.JK)."""
    bot = IDXTradingBot()

    # Sample standard input matching Layer 3.2 schema
    sample_bbca = CompanyProfile(
        ticker="BBCA.JK",
        company_name="Bank Central Asia Tbk",
        sector="Financials",
        current_price=9850.0,
        market_cap_idr=1_214_000_000_000_000,
        average_daily_turnover_idr=350_000_000_000,
        financials=FinancialData(
            pe_ratio=22.4,
            pbv_ratio=4.6,
            roe_percentage=21.5,
            roa_percentage=3.8,
            car_percentage=28.7,
            npm_percentage=42.1,
            revenue_yoy_growth=14.2,
            net_income_yoy_growth=15.8,
            fcf_positive=True,
            eps=440.0,
            bvps=2140.0,
            piotroski_score=8,
            altman_z_score=3.10,
        ),
        portfolio_context=PortfolioContext(available_cash_idr=50_000_000.0, average_buy_price=0.0),
    )

    result = bot.process_stock(sample_bbca)
    print("=== DECISION OUTPUT PAYLOAD (JSON) ===")
    print(json.dumps(result, indent=2))
    print("\n=== TELEGRAM ALERT PREVIEW ===")
    print(TelegramAlertAdapter.format_alert_message(result))


if __name__ == "__main__":
    run_sample_pipeline()
