"""
Live/demo trading loop.

By default this runs against WHATEVER account your DERIV_API_TOKEN belongs to --
make sure that token is a DEMO account token unless you deliberately pass --live
and have confirmed you want to risk real money.

Usage:
    python main.py --symbol R_100
    python main.py --symbol R_100 --live     # only after you're confident + confirmed
"""
import argparse
import asyncio
import time
import pandas as pd

from config import config
from deriv_client import DerivClient
from ml_signal import build_features, load_model
from strategy import decide
from risk import RiskState


async def run(symbol: str, live: bool):
    config.validate()
    model = load_model()

    client = DerivClient()
    await client.connect()

    if live and client.is_virtual:
        print("[main] --live was passed but this token is a DEMO account. "
              "Nothing dangerous will happen, but check your token if you meant real trading.")
    if not live and not client.is_virtual:
        print("[main] WARNING: this is a REAL account token but --live was not passed.")
        print("[main] Exiting without trading, to be safe. Pass --live to confirm real trading.")
        await client.close()
        return

    risk = RiskState()

    print(f"[main] Starting loop on {symbol}. Demo account: {client.is_virtual}. "
          f"Daily loss cap: {config.daily_loss_cap} {config.currency}")

    try:
        while risk.can_trade():
            candles = await client.get_candles(symbol, count=200, granularity=60)
            df = pd.DataFrame(candles)
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)

            feat_df = build_features(df)
            latest = feat_df.iloc[-1]
            decision = decide(latest, model)
            print(f"[main] {time.strftime('%H:%M:%S')} decision={decision.action} "
                  f"reason='{decision.reason}'")

            if decision.action in ("CALL", "PUT"):
                stake = risk.next_stake()
                buy_resp = await client.buy_contract(
                    contract_type=decision.action,
                    symbol=symbol,
                    stake=stake,
                    duration=config.duration,
                    duration_unit=config.duration_unit,
                )
                contract_id = buy_resp["contract_id"]
                print(f"[main] Bought contract {contract_id} for stake {stake}")

                profit = await client.get_contract_result(contract_id)
                print(f"[main] Contract {contract_id} closed. Profit: {profit}")
                risk.record_trade(profit)

            await asyncio.sleep(5)  # avoid hammering the API

        print(f"[main] Trading halted: {risk.halt_reason}")

    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=config.symbol)
    parser.add_argument("--live", action="store_true",
                         help="Confirm you want to trade with a REAL account token")
    args = parser.parse_args()

    asyncio.run(run(args.symbol, args.live))


if __name__ == "__main__":
    main()
