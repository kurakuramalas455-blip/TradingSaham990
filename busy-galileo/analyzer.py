"""Fundamental Analysis and Valuation Engine for IDX / BEI stocks."""

from datetime import datetime, timezone
import math
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class FinancialData(BaseModel):
    pe_ratio: Optional[float] = None
    pbv_ratio: Optional[float] = None
    roe_percentage: float = Field(..., description="ROE in % e.g. 21.5")
    roa_percentage: Optional[float] = None
    der_ratio: Optional[float] = Field(None, description="DER for non-financials e.g. 0.8")
    car_percentage: Optional[float] = Field(None, description="CAR for banking e.g. 28.7")
    npm_percentage: Optional[float] = None
    revenue_yoy_growth: Optional[float] = None
    net_income_yoy_growth: Optional[float] = None
    fcf_positive: bool = True
    current_holding_lots: int = 0
    eps: Optional[float] = None
    bvps: Optional[float] = None
    cfo_idr: Optional[float] = None
    net_income_idr: Optional[float] = None
    total_assets_idr: Optional[float] = None
    total_liabilities_idr: Optional[float] = None
    working_capital_idr: Optional[float] = None
    retained_earnings_idr: Optional[float] = None
    ebit_idr: Optional[float] = None
    book_value_equity_idr: Optional[float] = None
    piotroski_score: Optional[int] = None
    altman_z_score: Optional[float] = None


class PortfolioContext(BaseModel):
    available_cash_idr: float = 0.0
    average_buy_price: float = 0.0


class CompanyProfile(BaseModel):
    ticker: str
    company_name: str
    sector: str
    current_price: float
    market_cap_idr: float
    average_daily_turnover_idr: float
    is_fca: bool = False
    special_notations: List[str] = Field(default_factory=list)
    financials: FinancialData
    portfolio_context: PortfolioContext = Field(default_factory=PortfolioContext)


class ValuationSummary(BaseModel):
    fair_value_estimate: float
    margin_of_safety_percentage: float
    valuation_status: str


class ExecutionDetails(BaseModel):
    target_price: float
    order_type: str = "LIMIT"
    calculated_lots: int = 0
    estimated_cost_idr: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0


class DecisionOutput(BaseModel):
    timestamp: str
    ticker: str
    action: str  # BUY, SELL, HOLD, WATCHLIST, PASS
    confidence_score: int
    fundamental_score: int
    valuation_summary: ValuationSummary
    execution_details: ExecutionDetails
    analysis_rationale: List[str]
    risk_assessment: str


class FundamentalAnalyzer:
    """Evaluates IDX stock fundamentals, valuation, and generates trading decisions."""

    @staticmethod
    def calculate_altman_z_score(fin: FinancialData) -> float:
        """Calculate Altman Z''-Score for Emerging Markets:
        Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
        """
        if fin.altman_z_score is not None:
            return fin.altman_z_score

        if (
            fin.total_assets_idr
            and fin.total_assets_idr > 0
            and fin.total_liabilities_idr
            and fin.total_liabilities_idr > 0
        ):
            x1 = (fin.working_capital_idr or 0) / fin.total_assets_idr
            x2 = (fin.retained_earnings_idr or 0) / fin.total_assets_idr
            x3 = (fin.ebit_idr or (fin.net_income_idr or 0) * 1.25) / fin.total_assets_idr
            equity = fin.book_value_equity_idr or (fin.total_assets_idr - fin.total_liabilities_idr)
            x4 = equity / fin.total_liabilities_idr
            return round(6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4, 2)

        # Default safe approximation if fields omitted but profitable
        return 2.50 if (fin.roe_percentage >= 12 and (fin.der_ratio or 0) < 1.5) else 0.90

    @staticmethod
    def calculate_piotroski_f_score(fin: FinancialData) -> int:
        """Piotroski F-Score (0-9) heuristic/calculator."""
        if fin.piotroski_score is not None:
            return min(max(int(fin.piotroski_score), 0), 9)

        score = 0
        if fin.roe_percentage > 0:
            score += 1
        if (fin.roa_percentage or 0) > 0:
            score += 1
        if fin.fcf_positive:
            score += 1
        if fin.cfo_idr and fin.net_income_idr and fin.cfo_idr > fin.net_income_idr:
            score += 1
        if (fin.der_ratio or 0) <= 1.0:
            score += 1
        if (fin.npm_percentage or 0) >= 10:
            score += 1
        if (fin.net_income_yoy_growth or 0) > 0:
            score += 1
        if (fin.revenue_yoy_growth or 0) > 0:
            score += 1
        if (fin.car_percentage or 0) >= 18 or (fin.der_ratio or 0) < 1.2:
            score += 1
        return min(max(score, 0), 9)

    @staticmethod
    def estimate_fair_value(profile: CompanyProfile) -> float:
        """Multi-method fair value calculation (Graham Number + PBV/PER band heuristic)."""
        fin = profile.financials
        estimates = []

        # 1. Graham Number: sqrt(22.5 * EPS * BVPS)
        if fin.eps and fin.bvps and fin.eps > 0 and fin.bvps > 0:
            graham = math.sqrt(22.5 * fin.eps * fin.bvps)
            estimates.append(graham)

        # 2. Earnings multiplier (Fair P/E ~ 15x or industry fair)
        if fin.eps and fin.eps > 0:
            pe_fair = fin.eps * 15.0
            estimates.append(pe_fair)

        # 3. Book value multiplier (Fair P/B ~ 1.5x - 2.5x based on ROE)
        if fin.bvps and fin.bvps > 0:
            fair_pbv = max(1.2, fin.roe_percentage / 10.0)
            pbv_fair = fin.bvps * fair_pbv
            estimates.append(pbv_fair)

        # Fallback if raw per-share data is absent
        if not estimates:
            if fin.pe_ratio and fin.pe_ratio > 0:
                implied_fair = profile.current_price * (15.0 / fin.pe_ratio)
                estimates.append(implied_fair)
            else:
                estimates.append(profile.current_price * 1.15)

        return round(sum(estimates) / len(estimates), 2)

    def evaluate(self, profile: CompanyProfile) -> DecisionOutput:
        fin = profile.financials
        is_financial_sector = "financial" in profile.sector.lower() or "bank" in profile.sector.lower()
        rationale: List[str] = []

        # Step 1: Hard Filter Checks (Pass/Fail)
        disqualified = False
        reasons = []

        # Dangerous notations
        risky_notations = {"X", "E", "D", "M", "S", "B"}
        if profile.is_fca:
            disqualified = True
            reasons.append("Saham berada dalam Papan Pemantauan Khusus (FCA)")
        if any(n.upper() in risky_notations for n in profile.special_notations):
            disqualified = True
            reasons.append(f"Saham memiliki notasi khusus berisiko: {profile.special_notations}")

        # Liquidity Filter (Min Rp 1M daily turnover, target Rp 5M)
        if profile.average_daily_turnover_idr < 1_000_000_000:
            disqualified = True
            reasons.append(f"Likuiditas harian di bawah threshold minimum: Rp {profile.average_daily_turnover_idr:,.0f}")

        # ROE Filter
        if not is_financial_sector and fin.roe_percentage < 12.0:
            disqualified = True
            reasons.append(f"ROE {fin.roe_percentage:.1f}% di bawah standar 12%")

        # Solvency Filter
        if is_financial_sector:
            car = fin.car_percentage or 0.0
            if car < 14.0:
                disqualified = True
                reasons.append(f"CAR perbankan {car:.1f}% di bawah batas aman 14%")
        else:
            der = fin.der_ratio or 0.0
            if der >= 1.5:
                disqualified = True
                reasons.append(f"DER {der:.2f}x melebihi batas aman 1.5x")

        # Cash Flow & Bankruptcy score
        if not fin.fcf_positive:
            disqualified = True
            reasons.append("Free Cash Flow bernilai negatif")

        z_score = self.calculate_altman_z_score(fin)
        if z_score < 1.10:
            disqualified = True
            reasons.append(f"Altman Z-Score {z_score:.2f} berada di zona distress (< 1.10)")

        # Calculate Piotroski & Fair Value
        f_score = self.calculate_piotroski_f_score(fin)
        fair_value = self.estimate_fair_value(profile)
        mos_pct = round(((fair_value - profile.current_price) / fair_value) * 100, 2)
        val_status = "UNDERVALUED" if mos_pct >= 15 else ("OVERVALUED" if mos_pct < 0 else "FAIR")

        # Step 2: Pillar Scoring (0-100)
        p1_score = 0  # Profitability & Efficiency (30 pts)
        if fin.roe_percentage >= 18.0:
            p1_score += 15
            rationale.append(f"ROE sangat kuat di {fin.roe_percentage:.1f}% (>=18%)")
        elif fin.roe_percentage >= 12.0:
            p1_score += 10
            rationale.append(f"ROE solid di {fin.roe_percentage:.1f}% (>=12%)")

        npm = fin.npm_percentage or 0.0
        if npm >= 10.0:
            p1_score += 10
            rationale.append(f"Net Profit Margin tinggi ({npm:.1f}%)")
        elif npm >= 5.0:
            p1_score += 5

        if (fin.net_income_yoy_growth or 0.0) > 0:
            p1_score += 5
            rationale.append("Pertumbuhan laba bersih YoY positif")

        p2_score = 0  # Health & Quality (30 pts)
        if f_score >= 8:
            p2_score += 20
            rationale.append(f"Piotroski F-Score istimewa ({f_score}/9)")
        elif f_score >= 6:
            p2_score += 15
            rationale.append(f"Piotroski F-Score sehat ({f_score}/9)")
        else:
            p2_score += 10

        if fin.cfo_idr and fin.net_income_idr and fin.cfo_idr > fin.net_income_idr:
            p2_score += 10
            rationale.append("Kualitas laba prima (CFO > Net Income)")
        elif fin.fcf_positive:
            p2_score += 10

        p3_score = 0  # Valuation & MoS (40 pts)
        if mos_pct >= 30.0:
            p3_score += 25
            rationale.append(f"Margin of Safety sangat tinggi: {mos_pct:.1f}%")
        elif mos_pct >= 20.0:
            p3_score += 20
            rationale.append(f"Margin of Safety menarik: {mos_pct:.1f}%")
        elif mos_pct >= 15.0:
            p3_score += 10

        if (fin.pe_ratio or 999) <= 15.0 or (fin.pbv_ratio or 999) <= 2.0:
            p3_score += 15
            rationale.append(f"Valuasi relatif menarik (P/E: {fin.pe_ratio}, P/B: {fin.pbv_ratio})")

        total_fundamental_score = min(p1_score + p2_score + p3_score, 100)

        # Step 3: Determine Action
        timestamp_now = datetime.now(timezone.utc).isoformat()
        current_holding = fin.current_holding_lots

        if disqualified:
            action = "PASS"
            confidence = 15
            risk_ass = "HIGH_RISK"
            rationale.extend(reasons)
        elif current_holding > 0:
            # Check exit conditions
            if profile.current_price >= fair_value * 1.05:
                action = "SELL"
                confidence = 90
                rationale.append(f"Target Fair Value (Rp {fair_value:,.0f}) tercapai, profit taking.")
                risk_ass = "LOW_RISK"
            elif total_fundamental_score < 50 or f_score < 5:
                action = "SELL"
                confidence = 85
                rationale.append("Terjadi deteriorasi fundamental / Piotroski turun tajam.")
                risk_ass = "HIGH_RISK"
            else:
                action = "HOLD"
                confidence = 75
                rationale.append("Posisi masih dipertahankan dalam koridor wajar.")
                risk_ass = "LOW_RISK"
        else:
            # Entry conditions
            if total_fundamental_score >= 75 and mos_pct >= 15.0:
                action = "BUY"
                confidence = min(80 + int(mos_pct // 5), 95)
                risk_ass = "LOW_RISK"
            elif total_fundamental_score >= 60:
                action = "WATCHLIST"
                confidence = 65
                rationale.append("Fundamental bagus namun menunggu MoS atau konfirmasi momentum lebih optimal.")
                risk_ass = "MEDIUM_RISK"
            else:
                action = "PASS"
                confidence = 40
                rationale.append("Skor fundamental total belum mencukupi standar minimum.")
                risk_ass = "MEDIUM_RISK"

        return DecisionOutput(
            timestamp=timestamp_now,
            ticker=profile.ticker,
            action=action,
            confidence_score=confidence,
            fundamental_score=total_fundamental_score,
            valuation_summary=ValuationSummary(
                fair_value_estimate=fair_value,
                margin_of_safety_percentage=mos_pct,
                valuation_status=val_status,
            ),
            execution_details=ExecutionDetails(
                target_price=profile.current_price,
                order_type="LIMIT",
                calculated_lots=0,
                estimated_cost_idr=0.0,
                stop_loss_price=0.0,
                take_profit_price=fair_value,
            ),
            analysis_rationale=rationale,
            risk_assessment=risk_ass,
        )
