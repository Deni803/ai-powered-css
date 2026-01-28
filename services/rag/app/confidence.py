from __future__ import annotations


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_confidence(
    top_score: float | None,
    self_confidence: float | None,
    weight_retrieval: float = 0.6,
    weight_self: float = 0.4,
) -> float:
    if top_score is None and self_confidence is None:
        return 0.0

    if self_confidence is None:
        return clamp(top_score or 0.0)

    if top_score is None:
        return clamp(self_confidence)

    combined = (weight_retrieval * top_score) + (weight_self * self_confidence)
    return clamp(combined)
