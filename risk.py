"""
Guardrails so the bot can't silently blow through your account.
No martingale/stake-doubling logic here by design.
"""
from dataclasses import dataclass, field
from config import config


@dataclass
class RiskState:
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    halted: bool = False
    halt_reason: str = ""

    def record_trade(self, profit: float):
        self.trades_today += 1
        self.daily_pnl += profit
        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        self._check_limits()

    def _check_limits(self):
        if self.daily_pnl <= -abs(config.daily_loss_cap):
            self.halted = True
            self.halt_reason = f"Daily loss cap hit ({self.daily_pnl:.2f})"
        elif self.trades_today >= config.max_trades_per_day:
            self.halted = True
            self.halt_reason = f"Max trades/day reached ({self.trades_today})"
        elif self.consecutive_losses >= config.max_consecutive_losses:
            self.halted = True
            self.halt_reason = f"{self.consecutive_losses} consecutive losses"

    def next_stake(self) -> float:
        # Fixed stake by default. Martingale intentionally not implemented here --
        # if you add it later, understand it multiplies risk on losing streaks.
        return config.stake

    def can_trade(self) -> bool:
        return not self.halted
