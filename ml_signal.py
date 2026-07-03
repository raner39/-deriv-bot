"""
Feature engineering and a gradient-boosted classifier that predicts whether
the next candle closes up or down, given recent indicator/price features.

This is intentionally simple (short-horizon direction classifier), not a
guarantee of edge -- synthetic indices are close to random-walk with a
built-in house edge, so treat model output as ONE input, not gospel.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

from indicators import add_indicators

FEATURE_COLS = [
    "rsi", "ma_fast", "ma_slow", "bb_upper", "bb_mid", "bb_lower",
    "returns", "volatility",
]

MODEL_PATH = "model.joblib"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_indicators(df)
    # label: did the NEXT close go up (1) or down (0) vs current close?
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df = df.dropna().reset_index(drop=True)
    return df


def train(df: pd.DataFrame, save_path: str = MODEL_PATH):
    feat_df = build_features(df)
    X = feat_df[FEATURE_COLS]
    y = feat_df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False  # keep time order, no leakage
    )

    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.05, random_state=42
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    print(f"[ml_signal] Holdout accuracy: {acc:.3f} (0.5 = coin flip, be skeptical of much higher)")

    joblib.dump(model, save_path)
    print(f"[ml_signal] Model saved to {save_path}")
    return model, acc


def load_model(path: str = MODEL_PATH):
    return joblib.load(path)


def predict_proba_up(model, row: pd.Series) -> float:
    """Returns probability the next candle closes up, given current row features."""
    X = row[FEATURE_COLS].to_frame().T
    proba = model.predict_proba(X)[0]
    # class 1 = "up"
    classes = list(model.classes_)
    return proba[classes.index(1)]
