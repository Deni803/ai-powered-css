from __future__ import annotations

import re


_EN_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank",
    "ok",
    "okay",
    "good",
    "gm",
    "goodmorning",
    "goodafternoon",
    "goodevening",
}

_HI_GREETINGS = {
    "नमस्ते",
    "हाय",
    "हैलो",
    "धन्यवाद",
    "ठीक",
    "ओके",
    "सुप्रभात",
    "शुभ",
}


def _normalize(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\u0900-\u097F\s]", " ", text.lower())
    return [tok for tok in cleaned.split() if tok]


class EscalationPolicy:
    def __init__(self, conf_threshold: float, very_low_threshold: float = 0.2, min_len: int = 6):
        self.conf_threshold = conf_threshold
        self.very_low_threshold = very_low_threshold
        self.min_len = min_len

    def is_greeting(self, message: str) -> bool:
        tokens = _normalize(message)
        if not tokens:
            return True
        if len(tokens) <= 2:
            joined = "".join(tokens)
            if joined in _EN_GREETINGS or joined in _HI_GREETINGS:
                return True
        for tok in tokens:
            if tok in _EN_GREETINGS or tok in _HI_GREETINGS:
                return True
        return False

    def is_too_short(self, message: str) -> bool:
        return len(message.strip()) < self.min_len

    def should_answer(self, confidence: float) -> bool:
        return confidence >= self.conf_threshold

    def should_auto_escalate(self, confidence: float, message_len: int, low_conf_count: int) -> bool:
        if confidence < self.very_low_threshold and message_len > 12:
            return True
        return low_conf_count >= 2
