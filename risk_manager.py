"""Risk Management and Position Sizing for Indonesian Equity Market (IDX)."""

import math
from typing import Dict, Tuple
from config import settings


class IDXRiskManager:
    """Manages position sizing, IDX tick sizes, fees, and safety rules."""

    @staticmethod
    def get_tick_size(price: float) -> int:
        """Returns IDX standard tick size based on price tiers:
        - Price < 200: Rp 1
        - Price 200 - < 500: Rp 2
        - Price 500 - < 2000: Rp 5
        - Price 2000 - < 5000: Rp 10
        - Price >= 5000: Rp 25
        """
        if price < 200:
            return 1
        elif price < 500:
            return 2
        elif price < 2000:
            return 5
        elif price < 5000:
            return 10
        else:
            return 25

    @classmethod
    def align_to_tick(cls, price: float, round_direction: str = "nearest") -> int:
        """Rounds price to valid IDX tick."""
        if price <= 0:
            return 0
        tick = cls.get_tick_size(price)
        if round_direction == "down":
            aligned = math.floor(price / tick) * tick
        elif round_direction == "up":
            aligned = math.ceil(price / tick) * tick
        else:
            aligned = round(price / tick) * tick
        return int(max(aligned, tick))

    @staticmethod
    def calculate_buy_total_cost(price: float, lots: int) -> float:
        """Calculates total buy cost including broker fee, PPN, and exchange levy."""
        gross = price * lots * 100
        broker_fee_with_ppn = settings.BUY_BROKER_FEE_PCT * (1.0 + settings.PPN_PCT)
        total_fee_rate = broker_fee_with_ppn + settings.LEVY_PCT
        return round(gross * (1.0 + total_fee_rate), 2)

    @staticmethod
    def calculate_sell_net_proceeds(price: float, lots: int) -> float:
        """Calculates net proceeds from sell after broker fee, PPN, levy, and PPh Final (0.10%)."""
        gross = price * lots * 100
        broker_fee_with_ppn = settings.SELL_BROKER_FEE_PCT * (1.0 + settings.PPN_PCT)
        total_deduction_rate = broker_fee_with_ppn + settings.LEVY_PCT + settings.PPH_FINAL_PCT
        return round(gross * (1.0 - total_deduction_rate), 2)

    def calculate_position_size(
        self,
        entry_price: float,
        fair_value: float,
        portfolio_equity: float,
        available_cash: float,
        custom_stop_loss: float = 0.0,
    ) -> Tuple[int, int, int, float]:
        """Calculates (lots, stop_loss_price, take_profit_price, total_estimated_cost).
        Uses Fixed Fractional Risk sizing with IDX lot (100 shares) and portfolio safety limits.
        """
        aligned_entry = self.align_to_tick(entry_price)
        if aligned_entry <= 0:
            return (0, 0, 0, 0.0)

        # Default Stop Loss: ~7% below entry aligned to tick
        if custom_stop_loss > 0:
            aligned_sl = self.align_to_tick(custom_stop_loss, round_direction="down")
        else:
            raw_sl = aligned_entry * 0.93
            aligned_sl = self.align_to_tick(raw_sl, round_direction="down")

        # Ensure stop loss is strictly below entry
        if aligned_sl >= aligned_entry:
            aligned_sl = aligned_entry - self.get_tick_size(aligned_entry)

        # Take Profit aligned to tick
        aligned_tp = self.align_to_tick(max(fair_value, aligned_entry * 1.15), round_direction="up")

        # Fixed fractional risk per trade (e.g. 1.5%)
        risk_amount = portfolio_equity * settings.MAX_RISK_PER_TRADE
        risk_per_share = max(aligned_entry - aligned_sl, 1.0)
        risk_per_lot = risk_per_share * 100

        # Raw lot calculation based on risk
        calculated_lots = int(risk_amount // risk_per_lot)

        # Limit 1: Max single stock allocation limit (e.g. 15% of equity)
        max_cost_allowed = portfolio_equity * settings.MAX_SINGLE_STOCK_ALLOCATION
        max_lots_by_alloc = int(max_cost_allowed // (aligned_entry * 100))
        calculated_lots = min(calculated_lots, max_lots_by_alloc)

        # Limit 2: Available cash buffer constraint (keep at least CASH_BUFFER_PCT in cash)
        required_buffer = portfolio_equity * settings.CASH_BUFFER_PCT
        usable_cash = max(0.0, available_cash - required_buffer)
        max_lots_by_cash = int(usable_cash // (aligned_entry * 100 * 1.002))
        calculated_lots = min(calculated_lots, max_lots_by_cash)

        if calculated_lots <= 0:
            return (0, aligned_sl, aligned_tp, 0.0)

        total_cost = self.calculate_buy_total_cost(aligned_entry, calculated_lots)
        return (calculated_lots, aligned_sl, aligned_tp, total_cost)

    @staticmethod
    def check_circuit_breaker(daily_drawdown_pct: float) -> bool:
        """Returns True if daily drawdown exceeds limit (freezing new buy orders)."""
        return daily_drawdown_pct >= settings.DAILY_CIRCUIT_BREAKER_PCT
