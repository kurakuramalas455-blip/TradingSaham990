"""Configuration module for IDX trading and fundamental analysis bot."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Safety Switches
    DRY_RUN: bool = True
    ENABLE_LIVE_TRADING: bool = False

    # Broker & Credentials
    BROKER_USER_ID: str = ""
    BROKER_PASSWORD: str = ""
    BROKER_PIN: str = ""
    BROKER_SESSION_TOKEN: str = ""

    # Telegram Alerting
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Portfolio & Risk Limits
    INITIAL_CASH_IDR: float = 100_000_000.0
    MAX_SINGLE_STOCK_ALLOCATION: float = 0.15  # Max 15% per stock
    MAX_SECTOR_ALLOCATION: float = 0.25        # Max 25% per sector
    MAX_RISK_PER_TRADE: float = 0.015          # 1.5% fixed fractional risk
    CASH_BUFFER_PCT: float = 0.10             # 10% minimum cash buffer
    DAILY_CIRCUIT_BREAKER_PCT: float = 0.03   # 3% daily drawdown stop

    # IDX Fees & Taxes
    BUY_BROKER_FEE_PCT: float = 0.0015       # 0.15%
    SELL_BROKER_FEE_PCT: float = 0.0025      # 0.25%
    PPN_PCT: float = 0.11                     # 11% PPN on broker fee
    LEVY_PCT: float = 0.00043                 # 0.043% KPEI/KSEI/IDX
    PPH_FINAL_PCT: float = 0.0010             # 0.10% Final Tax on Sell

    # Risk-Free Rate for DCF (10Y Indonesia Gov Bond Yield)
    INDONESIA_RISK_FREE_RATE: float = 0.068

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
