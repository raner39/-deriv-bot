"""
Combines the rule-based indicator signal with the ML model's probability
estimate. Only produces a trade decision when BOTH layers agree -- this is
a deliberate filter to cut down on noisy/low-conviction trades.
"""
from dataclasses import dataclass
from indicators import rule_signal
from ml_signal import predict_proba_up
from config import config


@dataclass
class Decision:
    action: str          # "CALL", "PUT", or "HOLD"
    reason: str
    ml_confidence: float


def decide(row, model, confidence_threshold: float = None) -> Decision:
    threshold = confidence_threshold if confidence_threshold is not None else config.ml_confidence_threshold

    rb = rule_signal(row)
    proba_up = predict_proba_up(model, row)
    proba_down = 1 - proba_up

    ml_bias = "none"
    ml_conf = 0.0
    if proba_up >= threshold:
        ml_bias, ml_conf = "up", proba_up
    elif proba_down >= threshold:
        ml_bias, ml_conf = "down", proba_down

    if rb == "up" and ml_bias == "up":
        return Decision("CALL", f"RSI+MA bullish, ML confidence {ml_conf:.2f}", ml_conf)
    if rb == "down" and ml_bias == "down":
        return Decision("PUT", f"RSI+MA bearish, ML confidence {ml_conf:.2f}", ml_conf)

    return Decision("HOLD", f"No agreement (rules={rb}, ml_bias={ml_bias})", ml_conf)
