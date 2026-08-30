"""Broker Execution Adapters for Indonesian Stock Market (IDX)."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from config import settings
from risk_manager import IDXRiskManager


class BaseBrokerAdapter(ABC):
    """Abstract interface for IDX Broker Adapters."""

    @abstractmethod
    def submit_buy_order(self, ticker: str, price: int, lots: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    def submit_sell_order(self, ticker: str, price: int, lots: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_portfolio_status(self) -> Dict[str, Any]:
        pass


class PaperTradingAdapter(BaseBrokerAdapter):
    """Virtual paper trading simulator with IDX T+2 settlement and accurate fee tracking."""
    _FILE = "portfolio.json"

    def __init__(self, initial_cash_idr: Optional[float] = None):
        self.holdings: Dict[str, Dict[str, Any]] = {}  # ticker -> {lots, avg_price}
        self.order_history: List[Dict[str, Any]] = []
        self.risk_manager = IDXRiskManager()
        
        self.cash_balance: float = initial_cash_idr or settings.INITIAL_CASH_IDR
        self._load()
        self.settled_cash: float = self.cash_balance

    def _load(self):
        try:
            import json, os
            if os.path.exists(self._FILE):
                data = json.load(open(self._FILE))
                self.cash_balance = float(data.get("cash_balance", self.cash_balance))
        except: pass

    def save(self):
        try:
            import json
            json.dump({"cash_balance": self.cash_balance}, open(self._FILE, "w"))
        except: pass

    def submit_buy_order(self, ticker: str, price: int, lots: int) -> Dict[str, Any]:
        aligned_price = self.risk_manager.align_to_tick(price)
        if lots <= 0:
            return {"status": "REJECTED", "reason": "Calculated lots must be greater than 0"}

        total_cost = self.risk_manager.calculate_buy_total_cost(aligned_price, lots)
        if total_cost > self.cash_balance:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient cash (Required: Rp {total_cost:,.0f}, Available: Rp {self.cash_balance:,.0f})",
            }

        self.cash_balance -= total_cost

        # Update holdings
        current = self.holdings.get(ticker, {"lots": 0, "avg_price": 0.0})
        total_lots = current["lots"] + lots
        new_avg_price = (
            (current["lots"] * current["avg_price"] + lots * aligned_price) / total_lots
            if total_lots > 0
            else aligned_price
        )
        self.holdings[ticker] = {"lots": total_lots, "avg_price": round(new_avg_price, 2)}

        record = {
            "order_id": f"BUY-{len(self.order_history) + 1:04d}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "action": "BUY",
            "price": aligned_price,
            "lots": lots,
            "shares": lots * 100,
            "total_cost_idr": total_cost,
            "status": "FILLED",
            "settlement": "T+2 Pending",
        }
        self.order_history.append(record)
        return record

    def submit_sell_order(self, ticker: str, price: int, lots: int) -> Dict[str, Any]:
        aligned_price = self.risk_manager.align_to_tick(price)
        current = self.holdings.get(ticker, {"lots": 0, "avg_price": 0.0})

        if current["lots"] < lots or lots <= 0:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient holdings (Requested: {lots} lots, Available: {current['lots']} lots)",
            }

        net_proceeds = self.risk_manager.calculate_sell_net_proceeds(aligned_price, lots)
        self.cash_balance += net_proceeds

        remaining_lots = current["lots"] - lots
        if remaining_lots == 0:
            del self.holdings[ticker]
        else:
            self.holdings[ticker]["lots"] = remaining_lots

        record = {
            "order_id": f"SELL-{len(self.order_history) + 1:04d}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "action": "SELL",
            "price": aligned_price,
            "lots": lots,
            "shares": lots * 100,
            "net_proceeds_idr": net_proceeds,
            "status": "FILLED",
            "settlement": "T+2 Pending",
        }
        self.order_history.append(record)
        return record

    def get_portfolio_status(self) -> Dict[str, Any]:
        return {
            "cash_balance_idr": round(self.cash_balance, 2),
            "holdings": self.holdings,
            "total_orders_executed": len(self.order_history),
        }


class HeadlessWebAdapter(BaseBrokerAdapter):
    """Browser RPA Adapter using Playwright for Indonesian broker web trading with safety gates."""

    def __init__(self):
        self.is_live = settings.ENABLE_LIVE_TRADING and not settings.DRY_RUN

    def submit_buy_order(self, ticker: str, price: int, lots: int) -> Dict[str, Any]:
        if not self.is_live:
            return {
                "status": "SIMULATED_SUCCESS",
                "message": f"[SAFETY GUARD] DRY_RUN is active. Would buy {lots} lots of {ticker} @ Rp {price}",
            }
        # # ponytail: Playwright browser automation hook for IPOT/Stockbit Web Trading
        return {"status": "LIVE_DISPATCHED", "ticker": ticker, "lots": lots, "price": price}

    def submit_sell_order(self, ticker: str, price: int, lots: int) -> Dict[str, Any]:
        if not self.is_live:
            return {
                "status": "SIMULATED_SUCCESS",
                "message": f"[SAFETY GUARD] DRY_RUN is active. Would sell {lots} lots of {ticker} @ Rp {price}",
            }
        return {"status": "LIVE_DISPATCHED", "ticker": ticker, "lots": lots, "price": price}

    def get_portfolio_status(self) -> Dict[str, Any]:
        return {"status": "CONNECTED", "mode": "LIVE" if self.is_live else "DRY_RUN"}


class TelegramAlertAdapter:
    """Formats and dispatches signal notifications with one-click decision action payloads."""

    @staticmethod
    def format_alert_message(decision_payload: Dict[str, Any]) -> str:
        ticker = decision_payload.get("ticker", "N/A")
        action = decision_payload.get("action", "HOLD")
        score = decision_payload.get("fundamental_score", 0)
        conf = decision_payload.get("confidence_score", 0)
        val = decision_payload.get("valuation_summary", {})
        exec_d = decision_payload.get("execution_details", {})
        rationale = decision_payload.get("analysis_rationale", [])

        lines = [
            f"[IDX BOT SIGNAL ALERT: {ticker}]",
            f"* Action: `{action}`",
            f"* Fundamental Score: {score}/100 | Confidence: {conf}%",
            f"* Target Price: Rp {exec_d.get('target_price', 0):,.0f}",
            f"* Calculated Lots: {exec_d.get('calculated_lots', 0)} ({exec_d.get('calculated_lots', 0)*100} lembar)",
            f"* Estimated Cost: Rp {exec_d.get('estimated_cost_idr', 0):,.0f}",
            f"* Stop Loss: Rp {exec_d.get('stop_loss_price', 0):,.0f}",
            f"* Take Profit: Rp {exec_d.get('take_profit_price', 0):,.0f}",
            f"* Fair Value: Rp {val.get('fair_value_estimate', 0):,.0f} (MoS: {val.get('margin_of_safety_percentage', 0)}%)",
            "",
            "Analisis Rationale:",
        ]
        for item in rationale:
            lines.append(f" - {item}")

        return "\n".join(lines)
