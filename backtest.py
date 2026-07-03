"""
Backtest the combined rule+ML strategy against historical candles.
No real trades are placed -- this just simulates outcomes using the
historical price series so you can sanity-check the strategy first.

Usage:
    python backtest.py --symbol R_100 --count 3000
"""
import argparse
import asyncio
import pandas as pd

from config import config
from deriv_client import DerivClient
from ml_signal import build_features, load_model
from strategy import decide
from risk import RiskState


async def fetch_history_df(symbol: str, count: int, granularity: int) -> pd.DataFrame:
    client = DerivClient()
    await client.connect()
    try:
        candles = await client.get_candles(symbol, count=count, granularity=granularity)
    finally:
        await client.close()
    df = pd.DataFrame(candles)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    return df


def simulate(df: pd.DataFrame, model) -> dict:
    feat_df = build_features(df)
    risk = RiskState()
    wins, losses, trades = 0, 0, 0

    for i in range(len(feat_df) - 1):
        if risk.halted:
            break
        row = feat_df.iloc[i]
        decision = decide(row, model)
        if decision.action == "HOLD":
            continue

        actual_next_up = feat_df.iloc[i]["target"] == 1
        won = (decision.action == "CALL" and actual_next_up) or (
            decision.action == "PUT" and not actual_next_up
        )
        stake = risk.next_stake()
        # Simplified payout assumption (~85% return on win, matches typical
        # Deriv rise/fall payout ballpark -- replace with real contract payout if needed)
        profit = stake * 0.85 if won else -stake
        risk.record_trade(profit)
        trades += 1
        wins += int(won)
        losses += int(not won)

    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / trades if trades else 0.0,
        "final_pnl": risk.daily_pnl,
        "halted": risk.halted,
        "halt_reason": risk.halt_reason,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=config.symbol)
    parser.add_argument("--count", type=int, default=3000)
    parser.add_argument("--granularity", type=int, default=60)
    args = parser.parse_args()

    config.validate()
    model = load_model()

    df = asyncio.run(fetch_history_df(args.symbol, args.count, args.granularity))
    print(f"[backtest] Fetched {len(df)} candles for {args.symbol}")

    results = simulate(df, model)
    print("\n=== Backtest results ===")
    for k, v in results.items():
        print(f"{k}: {v}")
    print(
        "\nNote: this uses a simplified payout assumption and a single-symbol, "
        "single-timeframe backtest. Treat results as directional, not a guarantee "
        "of live performance."
    )


if __name__ == "__main__":
    main()
