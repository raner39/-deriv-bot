"""
Central configuration. Loads secrets from environment / .env file.
Never hardcode your API token here or anywhere else in the codebase.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    api_token: str = os.getenv("DERIV_API_TOKEN", "")
    app_id: str = os.getenv("DERIV_APP_ID", "1089")  # 1089 is Deriv's public demo app_id
    ws_url: str = "wss://ws.derivws.com/websockets/v3"

    # --- Trading params ---
    symbol: str = "R_100"
    contract_type_call: str = "CALL"   # "rises"
    contract_type_put: str = "PUT"     # "falls"
    duration: int = 5
    duration_unit: str = "t"           # 't' = ticks
    stake: float = 1.0                 # base stake in account currency
    currency: str = "USD"

    # --- Risk management (see risk.py) ---
    daily_loss_cap: float = 20.0       # stop trading for the day after losing this much
    max_trades_per_day: int = 30
    max_consecutive_losses: int = 4    # pause after this many losses in a row
    use_martingale: bool = False       # deliberately off by default

    # --- Strategy thresholds ---
    rsi_period: int = 14
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    ma_fast: int = 10
    ma_slow: int = 30
    ml_confidence_threshold: float = 0.60  # only trade if model is at least this confident

    def validate(self):
        if not self.api_token:
            raise ValueError(
                "DERIV_API_TOKEN is not set. Copy .env.example to .env and add your token."
            )


config = Config()
