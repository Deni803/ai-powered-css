from __future__ import annotations

from typing import Any
import re


def detect_language(text: str) -> str:
    for char in text:
        if "\u0900" <= char <= "\u097F":
            return "hi"
    return "en"


def detect_roman_hindi(text: str) -> bool:
    if not text.isascii():
        return False
    function_words = {
        "mujhe",
        "muje",
        "mera",
        "meri",
        "mere",
        "tum",
        "aap",
        "kya",
        "kaise",
        "kyu",
        "kyon",
        "nahi",
        "haan",
        "bhai",
        "kripya",
        "kripa",
        "ke",
        "ki",
        "ka",
        "ko",
        "se",
        "par",
        "mein",
        "liye",
        "bana",
        "do",
        "hai",
        "tha",
        "thi",
    }
    english_hints = {
        "refund",
        "refunds",
        "payment",
        "payments",
        "booking",
        "ticket",
        "status",
        "issue",
        "problem",
        "help",
        "confirmation",
        "cancel",
        "cancellation",
        "show",
        "movie",
        "event",
        "balance",
        "account",
        "amount",
        "discount",
        "price",
    }
    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    if not tokens:
        return False
    hindi_hits = sum(1 for tok in tokens if tok in function_words)
    english_hits = sum(1 for tok in tokens if tok in english_hints)
    return hindi_hits >= 2 and hindi_hits >= english_hits + 1


def build_system_prompt(language: str) -> str:
    if language == "hi":
        return (
            "You are BookMyShow support assistant. "
            "Answer ONLY using the provided context. "
            "If the context is insufficient, say you cannot confirm from the knowledge base and offer to create a support ticket here. "
            "Do NOT suggest live chat, email, WhatsApp, phone, or external channels unless explicitly mentioned in the context and directly relevant. "
            "Return a JSON object with keys: answer, self_confidence (0-1). "
            "Respond ONLY in Hindi (Devanagari). Do not include English."
        )
    return (
        "You are BookMyShow support assistant. "
        "Answer ONLY using the provided context. "
        "If the context is insufficient, say you cannot confirm from the knowledge base and offer to create a support ticket here. "
        "Do NOT suggest live chat, email, WhatsApp, phone, or external channels unless explicitly mentioned in the context and directly relevant. "
        "Return a JSON object with keys: answer, self_confidence (0-1). "
        "Respond in English."
    )


def build_user_prompt(
    user_query: str,
    context_chunks: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> str:
    history_block = ""
    if history:
        lines = []
        for item in history[-10:]:
            role = item.get("role", "user")
            content = (item.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        if lines:
            history_block = "Conversation History:\n" + "\n".join(lines) + "\n\n"
    if not context_chunks:
        context_block = "(no relevant context found)"
    else:
        lines = []
        for chunk in context_chunks:
            payload = chunk.get("payload", {})
            chunk_id = payload.get("chunk_id", chunk.get("id"))
            title = payload.get("title", "")
            text = payload.get("chunk_text", "")
            lines.append(f"[{chunk_id}] {title}\n{text}")
        context_block = "\n\n".join(lines)

    return (
        f"{history_block}"
        "Context:\n"
        f"{context_block}\n\n"
        "Question:\n"
        f"{user_query}\n\n"
        "Respond with JSON only."
    )


def fallback_answer(language: str, context_chunks: list[dict[str, Any]]) -> tuple[str, float]:
    if not context_chunks:
        if language == "hi":
            return (
                "मुझे नॉलेज बेस से पुष्टि नहीं मिल पाई। मैं यहां सपोर्ट टिकट बना सकता हूँ।",
                0.2,
            )
        return "I couldn't confirm this from the knowledge base. I can create a support ticket for you here.", 0.2

    payload = context_chunks[0].get("payload", {}) if context_chunks else {}
    text = payload.get("chunk_text", "")
    sentence = _first_sentence(text)
    if language == "hi":
        return f"उपलब्ध जानकारी के अनुसार: {sentence}", 0.4
    return f"Based on the available information: {sentence}", 0.4


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    for sep in [".", "।", "?", "!"]:
        if sep in text:
            return text.split(sep)[0].strip() + sep
    return text.strip()[:240]
