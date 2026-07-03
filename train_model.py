"""
Fetch historical candles from Deriv and train the ML direction-classifier.

Usage:
    python train_model.py --symbol R_100 --count 5000 --granularity 60
"""
import argparse
import asyncio
import pandas as pd

from config import config
from deriv_client import DerivClient
from ml_signal import train


async def fetch_history_df(symbol: str, count: int, granularity: int) -> pd.DataFrame:
    client = DerivClient()
    await client.connect()
    try:
        candles = await client.get_candles(symbol, count=count, granularity=granularity)
    finally:
        await client.close()
    df = pd.DataFrame(candles)
    df = df.rename(columns={"epoch": "epoch"})
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=config.symbol)
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--granularity", type=int, default=60, help="seconds per candle")
    args = parser.parse_args()

    config.validate()

    df = asyncio.run(fetch_history_df(args.symbol, args.count, args.granularity))
    print(f"[train_model] Fetched {len(df)} candles for {args.symbol}")

    train(df)


if __name__ == "__main__":
    main()
