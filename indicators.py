"""
Technical indicators computed on a pandas DataFrame of OHLC candles.
Expects columns: open, high, low, close (Deriv candle field names: open, high, low, close, epoch).
"""
import pandas as pd
import numpy as np


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def moving_average(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0):
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    return upper, ma, lower


def add_indicators(df: pd.DataFrame, rsi_period=14, ma_fast=10, ma_slow=30) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = rsi(df["close"], rsi_period)
    df["ma_fast"] = moving_average(df["close"], ma_fast)
    df["ma_slow"] = moving_average(df["close"], ma_slow)
    upper, mid, lower = bollinger_bands(df["close"])
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = upper, mid, lower
    df["returns"] = df["close"].pct_change()
    df["volatility"] = df["returns"].rolling(20).std()
    return df


def rule_signal(row) -> str:
    """
    Simple rule-based bias from indicator values in a single row.
    Returns 'up', 'down', or 'none'.
    """
    if pd.isna(row.get("rsi")) or pd.isna(row.get("ma_fast")) or pd.isna(row.get("ma_slow")):
        return "none"

    bullish = row["rsi"] < 30 and row["ma_fast"] > row["ma_slow"]
    bearish = row["rsi"] > 70 and row["ma_fast"] < row["ma_slow"]

    if bullish:
        return "up"
    if bearish:
        return "down"
    return "none"
