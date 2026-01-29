from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import md_to_html

from ai_powered_css.api.escalation import EscalationPolicy

_ROMAN_HI_FUNCTION_WORDS = {
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
    "haanji",
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

_ENGLISH_HINT_WORDS = {
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
    "confirm",
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

_SUPPORT_REQUEST_WORDS = {
    "ticket",
    "agent",
    "support",
    "helpdesk",
    "human",
    "call",
    "representative",
    "टिकट",
    "एजेंट",
    "सपोर्ट",
    "मदद",
    "कॉल",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


_REFUND_WORDS = {
    "refund",
    "refunds",
    "रिफंड",
    "रिफन्ड",
    "वापसी",
    "paisa",
    "paise",
}

_PAYMENT_WORDS = {
    "payment",
    "payments",
    "pay",
    "paid",
    "paisa",
    "paise",
    "upi",
    "card",
    "debit",
    "credit",
    "netbanking",
    "wallet",
    "gpay",
    "phonepe",
    "paytm",
    "bank",
    "भुगतान",
    "पेमेंट",
    "कार्ड",
    "यूपीआई",
}

_BOOKING_WORDS = {
    "booking",
    "बुकिंग",
    "ticket",
    "टिकट",
    "show",
}

_DOMAIN_WORDS = set().union(
    _REFUND_WORDS,
    _PAYMENT_WORDS,
    _BOOKING_WORDS,
    _ENGLISH_HINT_WORDS,
    {
        "transaction",
        "deducted",
        "blocked",
        "block",
        "seat",
        "seats",
        "order",
        "orders",
    },
)

_CLOSING_PATTERNS_EN = (
    r"\bthank you\b",
    r"\bthanks\b",
    r"\bthx\b",
    r"\bappreciate\b",
    r"\bthat helps\b",
    r"\bthis helps\b",
    r"\bissue resolved\b",
    r"\bresolved\b",
    r"\bsolved\b",
    r"\ball good\b",
    r"\bno further help\b",
)
_CLOSING_PATTERNS_HI = (
    r"धन्यवाद",
    r"थैंक यू",
    r"हो गया",
    r"समाधान हो गया",
    r"मदद मिली",
    r"सब ठीक",
    r"ठीक है धन्यवाद",
)
_CLOSING_NEGATIVE_PATTERNS = (
    r"\bbut\b",
    r"\bstill\b",
    r"\bnot\b",
    r"\bneed help\b",
    r"\bhelp me\b",
    r"\bissue\b",
    r"\bproblem\b",
    r"\bpending\b",
    r"नहीं",
    r"लेकिन",
    r"पर",
    r"समस्या",
    r"मदद चाहिए",
)

_ISSUE_PATTERNS = [
    {"amount", "deducted"},
    {"amount", "confirmation"},
    {"deducted", "confirmation"},
    {"refund", "received"},
    {"refund", "pending"},
    {"show", "cancelled"},
    {"show", "canceled"},
    {"wrong", "amount"},
    {"discount", "applied"},
    {"discount", "not"},
    {"confirmation", "not"},
    {"payment", "failed"},
    {"transaction", "failed"},
    {"payment", "declined"},
    {"पैसे", "कट"},
    {"रिफंड", "नहीं"},
    {"शो", "कैंसिल"},
    {"गलत", "अमाउंट"},
    {"डिस्काउंट", "नहीं"},
    {"कन्फर्मेशन", "नहीं"},
    {"पैसा", "कटा"},
    {"paisa", "kata"},
    {"paisa", "cut"},
    {"refund", "nahi"},
    {"confirmation", "nahi"},
    {"show", "cancel"},
    {"amount", "wrong"},
]

_QUICK_REPLY_OPTIONS = {
    "en": [
        {
            "label": "Amount deducted but no confirmation",
            "category": "payment",
            "subtype": "deducted_no_confirmation",
            "canonical": "Transaction didn't go through and seats appeared to be blocked. Payment deducted but no confirmation. What should I do?",
        },
        {
            "label": "Refund not received yet",
            "category": "refund",
            "subtype": "refund_not_received",
            "canonical": "Refund not received yet. What is the refund timeline and when should it reflect?",
        },
        {
            "label": "Show cancelled",
            "category": "refund",
            "subtype": "show_cancelled",
            "canonical": "Show cancelled. What is the refund process and timeline?",
        },
        {
            "label": "Wrong amount / discount not applied",
            "category": "payment",
            "subtype": "wrong_amount_discount",
            "canonical": "Wrong amount or discount not applied. How can I fix this?",
        },
    ],
    "hi": [
        {
            "label": "पैसे कट गए लेकिन कन्फर्मेशन नहीं आया",
            "category": "payment",
            "subtype": "deducted_no_confirmation",
            "canonical": "ट्रांजैक्शन पूरा नहीं हुआ और सीट्स ब्लॉक दिख रही हैं। पैसे कट गए लेकिन कन्फर्मेशन नहीं आया। आगे क्या करना चाहिए?",
        },
        {
            "label": "रिफंड अभी तक नहीं मिला",
            "category": "refund",
            "subtype": "refund_not_received",
            "canonical": "रिफंड अभी तक नहीं मिला। रिफंड का समय कितना होता है और कब तक दिखेगा?",
        },
        {
            "label": "शो कैंसिल हुआ",
            "category": "refund",
            "subtype": "show_cancelled",
            "canonical": "शो कैंसिल हुआ है। रिफंड प्रोसेस और टाइमलाइन क्या है?",
        },
        {
            "label": "गलत अमाउंट / डिस्काउंट नहीं मिला",
            "category": "payment",
            "subtype": "wrong_amount_discount",
            "canonical": "गलत अमाउंट कट गया या डिस्काउंट नहीं मिला। इसे कैसे ठीक करें?",
        },
    ],
}

RESOLUTION_ANSWERED = "ANSWERED"
RESOLUTION_NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
RESOLUTION_UNRESOLVED = "UNRESOLVED"

def _detect_language(text: str) -> str:
    for char in text:
        if "\u0900" <= char <= "\u097F":
            return "hi"
    return "en"


def _is_ascii(text: str) -> bool:
    return all(ord(ch) < 128 for ch in text)


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [tok for tok in cleaned.split() if tok]


def _roman_hindi_decision(text: str) -> str:
    # High-precision Roman Hindi detection to avoid false positives on English-only queries.
    if not _is_ascii(text):
        return "en"
    tokens = _tokenize(text)
    if not tokens:
        return "en"
    hindi_hits = sum(1 for tok in tokens if tok in _ROMAN_HI_FUNCTION_WORDS)
    english_hits = sum(1 for tok in tokens if tok in _ENGLISH_HINT_WORDS)
    if hindi_hits >= 2 and hindi_hits >= english_hits + 1:
        return "hi"
    if hindi_hits >= 1 and english_hits <= 1:
        return "ambiguous"
    return "en"


def _detect_roman_hindi(text: str) -> bool:
    return _roman_hindi_decision(text) == "hi"


def _has_any(text: str, words: set[str]) -> bool:
    tokens = _tokenize(text)
    return any(tok in words for tok in tokens)


def _detect_intent(text: str) -> str | None:
    if _has_any(text, _REFUND_WORDS):
        return "refund"
    if _has_any(text, _PAYMENT_WORDS):
        return "payment"
    if _has_any(text, _BOOKING_WORDS):
        return "booking"
    return None


def _explicit_support_request(text: str) -> bool:
    return _has_any(text, _SUPPORT_REQUEST_WORDS)


def _is_closing_message(text: str) -> bool:
    cleaned = text.strip().lower()
    if not cleaned:
        return False
    if _explicit_support_request(text):
        return False
    if "?" in text:
        return False
    for pattern in _CLOSING_NEGATIVE_PATTERNS:
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            return False
    for pattern in _CLOSING_PATTERNS_EN:
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            return True
    for pattern in _CLOSING_PATTERNS_HI:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def _is_off_topic(text: str) -> bool:
    """Detect queries outside the support domain to avoid random KB answers."""
    if _detect_intent(text):
        return False
    if _matches_issue_pattern(text):
        return False
    if _explicit_support_request(text):
        return False
    if _has_any(text, _DOMAIN_WORDS):
        return False
    return True


def _matches_issue_pattern(text: str) -> bool:
    tokens = set(_tokenize(text))
    if not tokens:
        return False
    for pattern in _ISSUE_PATTERNS:
        if pattern.issubset(tokens):
            return True
    return False


def _is_high_risk_issue(text: str, intent: str | None) -> bool:
    if intent not in ("payment", "refund"):
        return False
    if _matches_issue_pattern(text):
        return True
    tokens = set(_tokenize(text))
    if {"charged", "twice"}.issubset(tokens) or {"charged", "double"}.issubset(tokens):
        return True
    return False


def _is_language_choice(text: str) -> str | None:
    cleaned = text.strip().lower()
    if cleaned in {"english", "en"}:
        return "en"
    if cleaned in {"hindi", "हिंदी", "हिन्दी", "hi"}:
        return "hi"
    return None


def _greeting_reply(lang: str) -> str:
    if lang == "hi":
        return "नमस्ते! मैं आपकी बुकिंग, रिफंड, या पेमेंट से जुड़ी मदद कर सकता हूँ। आप किस बारे में पूछना चाहेंगे?"
    return "Hi! I can help with bookings, refunds, or payments. What would you like to know?"


def _closing_reply(lang: str) -> str:
    if lang == "hi":
        return "धन्यवाद! BookYourShow में मदद करने का अवसर देने के लिए आभारी हूँ। अगर आगे कोई सहायता चाहिए, तो बेझिझक बताइए।"
    return "Thank you for choosing BookYourShow! I’m glad I could help. If you need anything else, just let me know."


def _short_reply(lang: str) -> str:
    if lang == "hi":
        return "कृपया थोड़ा और विवरण दें ताकि मैं बेहतर मदद कर सकूँ।"
    return "Please share a bit more detail so I can help better."


def _clarify_reply(lang: str) -> str:
    if lang == "hi":
        return "मैं पूरी तरह सुनिश्चित नहीं हूँ। कृपया थोड़ा और विवरण दें। चाहें तो आप टिकट भी बना सकते हैं।"
    return "I’m not fully sure. Could you share a bit more detail? You can also create a ticket."


def _language_preference_prompt(lang: str) -> tuple[str, list[str]]:
    if lang == "hi":
        return "आप हिंदी या English में किस भाषा में जवाब चाहते हैं?", ["हिंदी", "English"]
    return "Do you prefer English or Hindi?", ["English", "Hindi"]


def _language_ack(lang: str) -> str:
    if lang == "hi":
        return "ठीक है, मैं हिंदी में जवाब दूंगा।"
    return "Got it. I will respond in English."


def _clarify_refund_payment(lang: str) -> tuple[str, list[str]]:
    if lang == "hi":
        return (
            "कृपया बताएं, समस्या किस तरह की है?",
            [
                "पैसे कट गए लेकिन कन्फर्मेशन नहीं आया",
                "रिफंड अभी तक नहीं मिला",
                "शो कैंसिल हुआ",
                "गलत अमाउंट / डिस्काउंट नहीं मिला",
            ],
        )
    return (
        "Could you share which issue you are facing?",
        [
            "Amount deducted but no confirmation",
            "Refund not received yet",
            "Show cancelled",
            "Wrong amount / discount not applied",
        ],
    )


def _get_quick_replies(lang: str) -> list[str]:
    options = _QUICK_REPLY_OPTIONS.get(lang, _QUICK_REPLY_OPTIONS["en"])
    return [opt["label"] for opt in options]


def _match_quick_reply(message: str) -> dict[str, str] | None:
    cleaned = message.strip().lower()
    for lang in ("en", "hi"):
        for opt in _QUICK_REPLY_OPTIONS.get(lang, []):
            if cleaned == opt["label"].strip().lower():
                return opt
    return None


def _is_followup_query(text: str) -> bool:
    tokens = set(_tokenize(text))
    if not tokens:
        return False
    followup = {
        "timeline",
        "time",
        "status",
        "when",
        "how",
        "howlong",
        "where",
        "track",
        "update",
        "day",
        "days",
        "week",
        "weeks",
        "month",
        "months",
        "late",
        "delayed",
        "delay",
        "pending",
        "since",
        "kab",
        "kabtak",
        "kabtak",
        "kitna",
        "kab",
        "kabtak",
        "kabtk",
        "kabhi",
        "कब",
        "कबतक",
        "स्थिति",
        "टाइमलाइन",
        "कहाँ",
        "कैसे",
        "कितना",
    }
    if any(tok in followup for tok in tokens):
        return True
    if any(tok.isdigit() for tok in tokens):
        return True
    return len(tokens) <= 3


def _expand_query_with_subtype(subtype: str, message: str, lang: str) -> str:
    for option in _QUICK_REPLY_OPTIONS.get(lang, []) + _QUICK_REPLY_OPTIONS.get("en", []):
        if option["subtype"] == subtype:
            canonical = option["canonical"]
            if _is_followup_query(message):
                if lang == "hi":
                    return f"{canonical} {message}"
                return f"{canonical} {message}"
            return canonical
    return message


def _is_vague_domain(message: str, intent: str | None) -> bool:
    if intent is None:
        return False
    tokens = _tokenize(message)
    if len(tokens) <= 2:
        return True
    return False


def _sanitize_answer(answer: str, lang: str) -> str:
    # Remove out-of-scope channel suggestions unless explicitly present in KB content.
    banned = [
        "live chat",
        "email",
        "whatsapp",
        "call us",
        "call",
        "helpline",
        "लाइव चैट",
        "ईमेल",
        "व्हाट्सऐप",
        "वॉट्सएप",
        "कॉल",
    ]
    lowered = answer.lower()
    if not any(term in lowered for term in banned):
        return answer

    parts = re.split(r"(?<=[.!?।])\s+", answer.strip())
    kept = [part for part in parts if not any(term in part.lower() for term in banned)]
    cleaned = " ".join(kept).strip()
    if cleaned:
        return cleaned
    if lang == "hi":
        return "अगर इससे समाधान नहीं होता, तो मैं यहां सपोर्ट टिकट बना सकता हूँ।"
    return "If this doesn't resolve it, I can create a support ticket for you here."


def _detail_prompt(lang: str) -> str:
    if lang == "hi":
        return "कृपया बुकिंग ID, भुगतान विधि और तारीख/समय बताएं ताकि मैं सही मदद कर सकूँ।"
    return "Please share your Booking ID, payment method, and date/time so I can help accurately."


def _offer_ticket_prompt(lang: str) -> str:
    if lang == "hi":
        return "मैं अभी इसे पुष्टि नहीं कर पाया। क्या आप चाहते हैं कि मैं सपोर्ट टिकट बना दूँ?"
    return "I couldn't confirm this from the knowledge base. Would you like me to create a support ticket?"


def _contact_request_prompt(lang: str) -> str:
    if lang == "hi":
        return "टिकट बनाने के लिए कृपया अपना ईमेल या फोन नंबर चैट में लिखें (इनमें से कोई एक)."
    return "To create a support ticket, please type your email or phone number here in chat (either one is enough)."


def _normalize_contact(
    customer_name: str | None,
    customer_email: str | None,
    customer_phone: str | None,
) -> tuple[str | None, str | None, str | None]:
    name = (customer_name or "").strip() or None
    email = (customer_email or "").strip().lower() or None
    phone_raw = (customer_phone or "").strip()
    phone_digits = re.sub(r"\D", "", phone_raw) if phone_raw else ""
    phone = phone_digits or None

    if email and not _EMAIL_RE.match(email):
        frappe.throw(_("Invalid email address."))
    if phone and len(phone) < 10:
        frappe.throw(_("Invalid phone number."))
    if not email and not phone:
        frappe.throw(_("Email or phone is required to create a ticket."))
    return name, email, phone


def _extract_contact_from_text(text: str) -> tuple[str | None, str | None, str | None]:
    """Best-effort contact extraction from user messages for chat-based ticket creation."""
    email_match = re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", text)
    email = email_match.group(0) if email_match else None
    phone_digits = re.sub(r"\D", "", text)
    phone = phone_digits if len(phone_digits) >= 10 else None
    name = None
    label_match = re.search(r"(?:name|naam)\s*[:=]\s*([A-Za-z]{2,30})", text, re.IGNORECASE)
    if label_match:
        name = label_match.group(1)
    name_match = re.search(r"(?:my name is|i am|i'm)\s+([A-Za-z]{2,20})", text, re.IGNORECASE)
    if name_match:
        name = name_match.group(1)
    return name, email, phone


def _extract_name_from_history(history: list[dict[str, str]]) -> str | None:
    """Infer a user name from earlier onboarding turns (best-effort)."""
    prompt_markers = [
        "what’s your name",
        "what's your name",
        "आपका नाम क्या है",
        "आपका नाम",
    ]
    for idx, item in enumerate(history):
        if item.get("role") != "assistant":
            continue
        content = (item.get("content") or "").lower()
        if not any(marker in content for marker in prompt_markers):
            continue
        for next_item in history[idx + 1 :]:
            if next_item.get("role") != "user":
                continue
            candidate = (next_item.get("content") or "").strip()
            if not candidate:
                continue
            # Accept short responses as a name (e.g., "deni").
            if 2 <= len(candidate) <= 30 and len(candidate.split()) <= 2:
                return candidate
            break
    # Fallback: look for explicit "my name is" in any user message.
    for item in history:
        if item.get("role") != "user":
            continue
        content = item.get("content") or ""
        match = re.search(r"(?:my name is|i am|i'm)\s+([A-Za-z]{2,20})", content, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _count_clarification_prompts(history: list[dict[str, str]]) -> int:
    phrases = [
        "Could you share which issue you are facing?",
        "कृपया बताएं, समस्या किस तरह की है?",
        "Please share your Booking ID, payment method, and date/time",
        "कृपया बुकिंग ID, भुगतान विधि और तारीख/समय बताएं",
        _clarify_reply("en"),
        _clarify_reply("hi"),
    ]
    count = 0
    for item in history:
        if item.get("role") != "assistant":
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if any(phrase in content for phrase in phrases):
            count += 1
    return count


def _needs_clarification(text: str) -> tuple[bool, str | None]:
    # Require key details for refund/payment before attempting escalation.
    intent = _detect_intent(text)
    if intent in ("refund", "payment"):
        if _matches_issue_pattern(text):
            return False, intent
        details = _extract_details(text)
        missing = not details["booking_id"] and not details["payment_method"] and not details["amount"]
        if missing:
            return True, intent
    if len(text.split()) <= 2 and intent:
        return True, intent
    return False, intent


def _get_env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _rag_settings() -> dict[str, Any]:
    # Centralize RAG client settings to keep behavior consistent across endpoints.
    return {
        "rag_url": os.getenv("RAG_URL", "http://rag:8001"),
        "rag_api_key": os.getenv("RAG_API_KEY", ""),
        "top_k": _get_env_int("TOP_K", 5),
    }


def _policy_settings() -> dict[str, Any]:
    # Escalation thresholds are env-driven for easy tuning without code changes.
    return {
        "conf_threshold": _get_env_float("CONF_THRESHOLD", 0.7),
        "very_low_threshold": _get_env_float("VERY_LOW_THRESHOLD", 0.2),
        "min_top_score": _get_env_float("MIN_TOP_SCORE", 0.35),
        "answer_top_score": _get_env_float("ANSWER_TOP_SCORE", 0.45),
        "max_attempts": _get_env_int("ESCALATION_MAX_ATTEMPTS", 2),
    }


def _get_session_doc(session_id: str | None):
    if not session_id:
        return None
    existing = frappe.db.get_value("AI CSS Chat Session", {"session_id": session_id}, "name")
    if not existing:
        return None
    return frappe.get_doc("AI CSS Chat Session", existing)


def _ensure_session(session_id: str | None, language: str, session_doc=None) -> tuple[str, str, Any]:
    # Create a session record on-demand; update preferred language if it changed.
    if session_doc is None:
        session_doc = _get_session_doc(session_id)

    if not session_doc:
        session_id = session_id or str(uuid.uuid4())
        doc = frappe.get_doc(
            {
                "doctype": "AI CSS Chat Session",
                "session_id": session_id,
                "language": language,
                "preferred_lang": language,
                "low_conf_count": 0,
                "clarification_count": 0,
                "last_resolution_state": RESOLUTION_ANSWERED,
                "issue_category": "",
                "issue_subtype": "",
                "last_escalation_offered": 0,
            }
        )
        doc.insert(ignore_permissions=True)
        return session_id, doc.name, doc

    changed = False
    if language and session_doc.language != language:
        session_doc.language = language
        changed = True
    if language and getattr(session_doc, "preferred_lang", None) != language:
        session_doc.preferred_lang = language
        changed = True
    if changed:
        session_doc.save(ignore_permissions=True)
    return session_id or session_doc.session_id, session_doc.name, session_doc


def _insert_message(
    session_name: str,
    role: str,
    content: str,
    confidence: float | None = None,
    sources: list[dict] | None = None,
):
    # Persist chat messages for history + polling retrieval.
    doc = frappe.get_doc(
        {
            "doctype": "AI CSS Chat Message",
            "session": session_name,
            "role": role,
            "content": content,
            "confidence": confidence,
            "sources_json": json.dumps(sources or [], ensure_ascii=False),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _publish_chat_message(
    session_id: str,
    message_doc,
    sources: list[dict] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    # Best-effort realtime publish; polling reads from DB via get_messages.
    payload = {
        "session_id": session_id,
        "message": {
            "id": message_doc.name,
            "role": message_doc.role,
            "content": message_doc.content,
            "confidence": message_doc.confidence,
            "sources": sources or [],
            "created_at": message_doc.creation,
        },
    }
    if extra:
        payload["message"].update(extra)
    frappe.publish_realtime(
        "ai_css_chat_message",
        payload,
        room="website",
        after_commit=True,
    )


def _fetch_history(session_name: str, limit: int = 20) -> list[dict[str, str]]:
    rows = frappe.get_all(
        "AI CSS Chat Message",
        filters={"session": session_name},
        fields=["role", "content", "creation"],
        order_by="creation desc",
        limit=limit,
        ignore_permissions=True,
    )
    rows.reverse()
    history = []
    for row in rows:
        role = row.get("role")
        content = (row.get("content") or "").strip()
        if role and content:
            history.append({"role": role, "content": content})
    return history


def _update_session_state(
    session_doc,
    low_conf_count=None,
    clarification_count=None,
    last_resolution_state=None,
    issue_category=None,
    issue_subtype=None,
    last_escalation_offered=None,
    preferred_lang=None,
):
    changed = False
    if low_conf_count is not None and getattr(session_doc, "low_conf_count", None) != low_conf_count:
        session_doc.low_conf_count = low_conf_count
        changed = True
    if clarification_count is not None and getattr(session_doc, "clarification_count", None) != clarification_count:
        session_doc.clarification_count = clarification_count
        changed = True
    if last_resolution_state and getattr(session_doc, "last_resolution_state", None) != last_resolution_state:
        session_doc.last_resolution_state = last_resolution_state
        changed = True
    if issue_category is not None and getattr(session_doc, "issue_category", None) != issue_category:
        session_doc.issue_category = issue_category
        changed = True
    if issue_subtype is not None and getattr(session_doc, "issue_subtype", None) != issue_subtype:
        session_doc.issue_subtype = issue_subtype
        changed = True
    if last_escalation_offered is not None and getattr(session_doc, "last_escalation_offered", None) != (
        1 if last_escalation_offered else 0
    ):
        session_doc.last_escalation_offered = 1 if last_escalation_offered else 0
        changed = True
    if preferred_lang and getattr(session_doc, "preferred_lang", None) != preferred_lang:
        session_doc.preferred_lang = preferred_lang
        changed = True
    if changed:
        session_doc.save(ignore_permissions=True)


def _last_assistant_entry(session_name: str) -> dict[str, Any]:
    rows = frappe.get_all(
        "AI CSS Chat Message",
        filters={"session": session_name, "role": "assistant"},
        fields=["sources_json", "confidence", "creation"],
        order_by="creation desc",
        limit=1,
        ignore_permissions=True,
    )
    if not rows:
        return {"sources": [], "confidence": None}
    raw = rows[0].get("sources_json") or "[]"
    try:
        sources = json.loads(raw)
    except Exception:
        sources = []
    return {"sources": sources, "confidence": rows[0].get("confidence")}


def _last_assistant_sources(session_name: str) -> list[dict]:
    return _last_assistant_entry(session_name).get("sources") or []


def _last_user_message(session_name: str) -> str:
    rows = frappe.get_all(
        "AI CSS Chat Message",
        filters={"session": session_name, "role": "user"},
        fields=["content", "creation"],
        order_by="creation desc",
        limit=1,
        ignore_permissions=True,
    )
    if not rows:
        return ""
    return (rows[0].get("content") or "").strip()


def _top_score_from_sources(sources: list[dict]) -> float | None:
    if not sources:
        return None
    try:
        return float(max(item.get("score") or 0.0 for item in sources))
    except Exception:
        return None


def _evaluate_sources(sources: list[dict], min_top_score: float) -> tuple[list[dict], float, bool]:
    # Filter weak sources to avoid answering without evidence.
    if not sources:
        return [], 0.0, False
    try:
        top_score = max(float(item.get("score") or 0.0) for item in sources)
    except Exception:
        top_score = 0.0
    usable = top_score >= min_top_score
    return sources, top_score, usable


def _ticket_created_reply(lang: str, ticket_id: str | None) -> str:
    if lang == "hi":
        if ticket_id:
            return f"🎫 आपका टिकट बन गया है: #{ticket_id}. हमारी टीम 24 घंटे के भीतर आपसे संपर्क करेगी।"
        return "टिकट बनाने में समस्या हुई। कृपया थोड़ी देर बाद फिर से प्रयास करें।"
    if ticket_id:
        return f"Ticket created. Your ticket ID is #{ticket_id}. Our agent will contact you within 24 hours."
    return "Unable to create a ticket right now. Please try again later."


def _create_ticket_for_session(
    history: list[dict[str, str]],
    message: str,
    sources: list[dict],
    metadata: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    # Prefer HD Ticket; allow ToDo fallback only when explicitly enabled.
    allow_todo = os.getenv("ESCALATION_FALLBACK", "").lower() == "todo"
    if frappe.db.exists("DocType", "HD Ticket"):
        doctype = "HD Ticket"
    elif allow_todo:
        doctype = "ToDo"
    else:
        return None, None
    subject = _build_ticket_subject(message)
    ticket_type, ticket_id = _create_ticket(doctype, subject, history, sources, message, metadata=metadata)
    return ticket_type, ticket_id


def _handle_unresolved(
    session_id: str,
    session_name: str,
    session_doc,
    history: list[dict[str, str]],
    message: str,
    language: str,
    sources: list[dict] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sources = sources or []
    answer = _contact_request_prompt(language)
    escalated = False
    ticket_id = None
    ticket_type = None
    assistant_doc = _insert_message(session_name, "assistant", answer, confidence=0.0, sources=sources)
    _update_session_state(
        session_doc,
        low_conf_count=0,
        clarification_count=0,
        last_resolution_state=RESOLUTION_UNRESOLVED,
        last_escalation_offered=False,
        preferred_lang=language,
    )
    _publish_chat_message(
        session_id,
        assistant_doc,
        sources=sources,
        extra={
            "language": language,
            "resolution_state": RESOLUTION_UNRESOLVED,
            "escalation_offered": False,
            "contact_required": True,
            "ticket_id": ticket_id,
            "ticket_type": ticket_type,
        },
    )
    return {
        "session_id": session_id,
        "answer": answer,
        "confidence": 0.0,
        "language": language,
        "sources": sources,
        "resolution_state": RESOLUTION_UNRESOLVED,
        "quick_replies": [],
        "escalated": escalated,
        "escalation_offered": False,
        "contact_required": True,
        "ticket_id": ticket_id,
        "ticket_type": ticket_type,
    }


def _extract_details(text: str) -> dict[str, str]:
    # Lightweight entity extraction for ticket summaries (best-effort).
    booking_id = ""
    transaction_id = ""
    amount = ""
    payment_method = ""
    datetime_info = ""
    location = ""

    booking_match = re.search(r"\b[A-Za-z]{1,3}\d{6,12}\b", text)
    if booking_match:
        booking_id = booking_match.group(0)

    transaction_match = re.search(r"\b(?:txn|transaction)[-_\s]?\w{4,}\b", text, re.IGNORECASE)
    if transaction_match:
        transaction_id = transaction_match.group(0)

    amount_match = re.search(r"(₹\s?\d{2,6}|\b\d{2,6}\s?(?:rs|inr|rupees)\b)", text, re.IGNORECASE)
    if amount_match:
        amount = amount_match.group(0)

    if _has_any(text, {"upi", "यूपीआई"}):
        payment_method = "UPI"
    elif _has_any(text, {"card", "credit", "debit", "कार्ड"}):
        payment_method = "Card"
    elif _has_any(text, {"netbanking", "bank"}):
        payment_method = "Netbanking"
    elif _has_any(text, {"wallet", "paytm", "gpay", "phonepe"}):
        payment_method = "Wallet"

    date_match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
    if date_match:
        datetime_info = date_match.group(0)
    elif _has_any(text, {"today", "yesterday", "आज", "कल"}):
        datetime_info = "relative date mentioned"

    location_match = re.search(r"\b(?:in|at)\s+([A-Za-z]{3,20})\b", text, re.IGNORECASE)
    if location_match:
        location = location_match.group(1)
    hindi_location_match = re.search(r"में\s+([^\s]{2,20})", text)
    if hindi_location_match:
        location = hindi_location_match.group(1)

    return {
        "booking_id": booking_id,
        "transaction_id": transaction_id,
        "payment_method": payment_method,
        "amount": amount,
        "datetime_info": datetime_info,
        "location": location,
    }


def _guess_issue_type(text: str) -> str:
    if _has_any(text, _REFUND_WORDS):
        return "Refund"
    if _has_any(text, _PAYMENT_WORDS):
        return "Payment"
    if _has_any(text, {"cancel", "cancellation", "रद्द"}):
        return "Cancellation"
    if _has_any(text, _BOOKING_WORDS):
        return "Booking"
    return "Support"


def _build_ticket_subject(text: str) -> str:
    issue = _guess_issue_type(text)
    lower = text.lower()
    if "deduct" in lower or "कट" in text:
        return f"{issue} issue - amount deducted but no confirmation"
    if "refund" in lower or "रिफंड" in text:
        return f"{issue} issue - refund pending"
    return f"{issue} issue"


def _ticket_description(
    history: list[dict[str, str]],
    sources: list[dict],
    user_text: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    # Keep ticket body scannable in Helpdesk with explicit sections + newlines.
    details = _extract_details(user_text)
    metadata = metadata or {}
    session_id = metadata.get("session_id") or "n/a"
    language = metadata.get("language") or "n/a"
    resolution_state = metadata.get("resolution_state") or "n/a"
    confidence = metadata.get("confidence")
    top_score = metadata.get("top_score")
    customer_name = metadata.get("customer_name") or "Not provided"
    customer_email = metadata.get("customer_email") or "Not provided"
    customer_phone = metadata.get("customer_phone") or "Not provided"

    latest_message = (user_text or "").strip() or "Not provided"
    summary_lines = [
        "### Customer Details",
        f"- Name: {customer_name}",
        f"- Email: {customer_email}",
        f"- Phone: {customer_phone}",
        "",
        "### Issue Summary",
        f"- Category: {_guess_issue_type(user_text)}",
        f"- Customer’s latest message: {latest_message}",
        f"- Booking ID: {details['booking_id'] or 'Not provided'}",
        f"- Transaction ID: {details['transaction_id'] or 'Not provided'}",
        f"- Payment method: {details['payment_method'] or 'Not provided'}",
        f"- Date/time: {details['datetime_info'] or 'Not provided'}",
        f"- Amount: {details['amount'] or 'Not provided'}",
        f"- City/Venue: {details['location'] or 'Not provided'}",
        "",
        "### Conversation Transcript",
    ]

    for item in history[-12:]:
        role = "Customer" if item.get("role") == "user" else "Assistant"
        content = (item.get("content") or "").strip()
        summary_lines.append(f"- {role}: {content}")

    summary_lines.append("")
    summary_lines.append("### Knowledge Base Sources Used")
    if sources:
        for source in sources[:3]:
            title = source.get("title") or source.get("doc_id") or "Source"
            url = source.get("source_url") or "n/a"
            score = source.get("score")
            summary_lines.append(f"- {title} — {url} (score={score})")
    else:
        summary_lines.append("- Not available")

    summary_lines.append("")
    summary_lines.append("### System Metadata")
    summary_lines.append(f"- Session ID: {session_id}")
    summary_lines.append(f"- Language: {language}")
    summary_lines.append(f"- Resolution state: {resolution_state}")
    summary_lines.append(f"- Confidence: {confidence if confidence is not None else 'n/a'}")
    summary_lines.append(f"- Top score: {top_score if top_score is not None else 'n/a'}")

    return "\n".join(summary_lines)


def _create_ticket(
    doctype: str,
    subject: str,
    history: list[dict[str, str]],
    sources: list[dict],
    user_text: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, str]:
    # Escalate privileges for guest ticket creation while preserving the original user context.
    # Ensure we never restore to a None user; Frappe expects a real session user.
    current_user = frappe.session.user or "Guest"
    previous_ignore = getattr(frappe.flags, "ignore_permissions", False)
    try:
        frappe.flags.ignore_permissions = True
        frappe.local.flags.ignore_permissions = True
        frappe.set_user("Administrator")
        frappe.local.session.user = "Administrator"
        frappe.session.user = "Administrator"
        description_md = _ticket_description(history=history, sources=sources, user_text=user_text, metadata=metadata)
        description_html = md_to_html(description_md)

        def resolve_priority() -> str | None:
            # Helpdesk priority doctype can vary; choose a safe default if present.
            if doctype != "HD Ticket":
                return "Medium"
            if frappe.db.exists("DocType", "HD Ticket Priority"):
                if frappe.db.exists("HD Ticket Priority", "Medium"):
                    return "Medium"
                names = frappe.get_all("HD Ticket Priority", pluck="name", limit=1) or []
                if names:
                    return names[0]
            return None

        def build_payload(doctype: str) -> dict[str, Any]:
            # Keep payload minimal and compatible across HD Ticket and ToDo.
            if doctype == "ToDo":
                return {
                    "doctype": doctype,
                    "description": f"{subject}\n\n{description_md}",
                    "status": "Open",
                    "priority": "Medium",
                }
            payload = {
                "doctype": doctype,
                "subject": subject,
                "description": description_html,
                "status": "Open",
            }
            priority = resolve_priority()
            if priority:
                payload["priority"] = priority
            return payload

        doc = frappe.get_doc(build_payload(doctype))
        def _coerce_uuid(value):
            # Some hooks serialize UUIDs; ensure they are JSON-friendly for Postgres.
            if isinstance(value, uuid.UUID):
                return str(value)
            if isinstance(value, dict):
                return {k: _coerce_uuid(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [_coerce_uuid(v) for v in value]
            return value

        for field, value in doc.as_dict().items():
            coerced = _coerce_uuid(value)
            if coerced is not value:
                doc.set(field, coerced)
        doc.flags.ignore_permissions = True
        doc.flags.ignore_validate = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doctype, doc.name
    finally:
        frappe.set_user(current_user)
        frappe.local.session.user = current_user
        frappe.flags.ignore_permissions = previous_ignore


@frappe.whitelist(allow_guest=True)
def send_message(session_id: str | None = None, message: str | None = None, lang_hint: str | None = None):
    previous_ignore = getattr(frappe.flags, "ignore_permissions", False)
    previous_user = frappe.session.user or "Guest"
    frappe.flags.ignore_permissions = True
    frappe.set_user("Administrator")
    try:
        if not message or not message.strip():
            frappe.throw(_("message is required"))

        message = message.strip()
        if lang_hint in ("auto", ""):
            lang_hint = None

        existing_doc = _get_session_doc(session_id)
        preferred_lang = getattr(existing_doc, "preferred_lang", None) if existing_doc else None
        forced_lang = lang_hint if lang_hint in ("en", "hi") else None

        # Language selection: forced mode overrides, then Devanagari, then Roman Hindi, then default EN.
        has_devanagari = _detect_language(message) == "hi"
        roman_decision = _roman_hindi_decision(message) if not forced_lang else "en"
        roman_hindi = roman_decision == "hi"
        ambiguous_language = roman_decision == "ambiguous" and not has_devanagari and not preferred_lang

        if forced_lang:
            language = forced_lang
        elif has_devanagari or roman_decision == "hi":
            language = "hi"
        elif preferred_lang:
            language = preferred_lang
        else:
            language = "en"

        session_id, session_name, session_doc = _ensure_session(session_id, language, existing_doc)
        user_doc = _insert_message(session_name, "user", message)
        _publish_chat_message(
            session_id,
            user_doc,
            sources=[],
            extra={"language": language},
        )

        # If we previously asked for contact details, try to create the ticket from chat input.
        last_state = getattr(session_doc, "last_resolution_state", None)
        if last_state == RESOLUTION_UNRESOLVED:
            name, email, phone = _extract_contact_from_text(message)
            if email or phone:
                prev_user = frappe.session.user
                prev_ignore = getattr(frappe.flags, "ignore_permissions", False)
                prev_local_ignore = getattr(frappe.local.flags, "ignore_permissions", False)
                frappe.flags.ignore_permissions = True
                frappe.local.flags.ignore_permissions = True
                frappe.set_user("Administrator")
                frappe.local.session.user = "Administrator"
                frappe.session.user = "Administrator"
                try:
                    last_entry = _last_assistant_entry(session_name)
                    sources = last_entry.get("sources") or []
                    confidence = last_entry.get("confidence")
                    top_score = _top_score_from_sources(sources)
                    history = _fetch_history(session_name, limit=20)
                    if not name:
                        name = _extract_name_from_history(history)
                    name, email, phone = _normalize_contact(name, email, phone)
                    metadata = {
                        "session_id": session_id,
                        "language": language,
                        "resolution_state": RESOLUTION_UNRESOLVED,
                        "confidence": confidence,
                        "top_score": top_score,
                        "customer_name": name,
                        "customer_email": email,
                        "customer_phone": phone,
                    }
                    ticket_type, ticket_id = _create_ticket_for_session(history, message, sources, metadata=metadata)
                finally:
                    frappe.flags.ignore_permissions = prev_ignore
                    frappe.local.flags.ignore_permissions = prev_local_ignore
                    frappe.set_user(prev_user)
                    frappe.local.session.user = prev_user
                    frappe.session.user = prev_user

                answer = _ticket_created_reply(language, ticket_id)
                assistant_doc = _insert_message(session_name, "assistant", answer, confidence=0.0, sources=sources)
                _update_session_state(
                    session_doc,
                    low_conf_count=0,
                    clarification_count=0,
                    last_resolution_state=RESOLUTION_UNRESOLVED,
                    last_escalation_offered=False,
                    preferred_lang=language,
                )
                _publish_chat_message(
                    session_id,
                    assistant_doc,
                    sources=sources,
                    extra={
                        "language": language,
                        "resolution_state": RESOLUTION_UNRESOLVED,
                        "escalation_offered": False,
                        "contact_required": False,
                        "ticket_id": ticket_id,
                        "ticket_type": ticket_type,
                    },
                )
                return {
                    "session_id": session_id,
                    "answer": answer,
                    "confidence": 0.0,
                    "language": language,
                    "sources": sources,
                    "resolution_state": RESOLUTION_UNRESOLVED,
                    "quick_replies": [],
                    "escalated": True,
                    "escalation_offered": False,
                    "contact_required": False,
                    "ticket_id": ticket_id,
                    "ticket_type": ticket_type,
                }
            # No contact detected: prompt again and skip RAG.
            answer = _contact_request_prompt(language)
            assistant_doc = _insert_message(session_name, "assistant", answer, confidence=0.0, sources=[])
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=[],
                extra={
                    "language": language,
                    "resolution_state": RESOLUTION_UNRESOLVED,
                    "escalation_offered": False,
                    "contact_required": True,
                },
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "confidence": 0.0,
                "language": language,
                "sources": [],
                "resolution_state": RESOLUTION_UNRESOLVED,
                "quick_replies": [],
                "escalated": False,
                "escalation_offered": True,
                "contact_required": True,
                "ticket_id": None,
                "ticket_type": None,
            }

        language_choice = _is_language_choice(message)
        if language_choice:
            # Explicit language toggle by user.
            answer = _language_ack("hi" if language_choice == "hi" else "en")
            assistant_doc = _insert_message(session_name, "assistant", answer, confidence=None, sources=[])
            _update_session_state(
                session_doc,
                low_conf_count=0,
                clarification_count=0,
                last_resolution_state=RESOLUTION_ANSWERED,
                last_escalation_offered=False,
                preferred_lang=language_choice,
            )
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=[],
                extra={
                    "language": language_choice,
                    "resolution_state": RESOLUTION_ANSWERED,
                    "escalation_offered": False,
                    "quick_replies": [],
                },
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "confidence": 1.0,
                "language": language_choice,
                "sources": [],
                "resolution_state": RESOLUTION_ANSWERED,
                "quick_replies": [],
                "escalated": False,
                "escalation_offered": False,
                "ticket_id": None,
                "ticket_type": None,
            }

        if ambiguous_language:
            # Ask user to choose language instead of guessing.
            prompt, quick_replies = _language_preference_prompt("en")
            assistant_doc = _insert_message(session_name, "assistant", prompt, confidence=None, sources=[])
            _update_session_state(
                session_doc,
                low_conf_count=0,
                clarification_count=0,
                last_resolution_state=RESOLUTION_NEEDS_CLARIFICATION,
                last_escalation_offered=False,
            )
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=[],
                extra={
                    "language": "en",
                    "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                    "escalation_offered": False,
                    "quick_replies": quick_replies,
                },
            )
            return {
                "session_id": session_id,
                "answer": prompt,
                "confidence": 0.0,
                "language": "en",
                "sources": [],
                "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                "quick_replies": quick_replies,
                "escalated": False,
                "escalation_offered": False,
                "ticket_id": None,
                "ticket_type": None,
            }

        policy_settings = _policy_settings()
        policy = EscalationPolicy(
            conf_threshold=policy_settings["conf_threshold"],
            very_low_threshold=policy_settings["very_low_threshold"],
            min_len=6,
        )

        history = _fetch_history(session_name, limit=20)
        clarification_attempts = _count_clarification_prompts(history)
        clarification_count = int(getattr(session_doc, "clarification_count", 0) or 0)
        prior_low_conf = int(getattr(session_doc, "low_conf_count", 0) or 0)
        user_turns = sum(1 for item in history if item.get("role") == "user")

        if _explicit_support_request(message):
            # Honor explicit ticket request and move directly to contact collection.
            last_entry = _last_assistant_entry(session_name)
            sources = last_entry.get("sources") or []
            metadata = {
                "session_id": session_id,
                "language": language,
                "resolution_state": RESOLUTION_UNRESOLVED,
                "confidence": last_entry.get("confidence"),
                "top_score": _top_score_from_sources(sources),
            }
            return _handle_unresolved(
                session_id,
                session_name,
                session_doc,
                history,
                message,
                language,
                sources=sources,
                metadata=metadata,
            )

        if _is_closing_message(message):
            # Closing acknowledgements end the conversation without RAG or escalation.
            answer = _closing_reply(language)
            assistant_doc = _insert_message(session_name, "assistant", answer, confidence=None, sources=[])
            _update_session_state(
                session_doc,
                low_conf_count=0,
                clarification_count=0,
                last_resolution_state=RESOLUTION_ANSWERED,
                last_escalation_offered=False,
                preferred_lang=language,
            )
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=[],
                extra={
                    "language": language,
                    "resolution_state": RESOLUTION_ANSWERED,
                    "escalation_offered": False,
                    "quick_replies": [],
                },
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "confidence": 1.0,
                "language": language,
                "sources": [],
                "resolution_state": RESOLUTION_ANSWERED,
                "quick_replies": [],
                "escalated": False,
                "escalation_offered": False,
                "ticket_id": None,
                "ticket_type": None,
            }

        if policy.is_greeting(message):
            # Greetings are handled without RAG or escalation.
            answer = _greeting_reply(language)
            assistant_doc = _insert_message(session_name, "assistant", answer, confidence=None, sources=[])
            _update_session_state(
                session_doc,
                low_conf_count=0,
                clarification_count=0,
                last_resolution_state=RESOLUTION_ANSWERED,
                last_escalation_offered=False,
                preferred_lang=language,
            )
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=[],
                extra={
                    "language": language,
                    "resolution_state": RESOLUTION_ANSWERED,
                    "escalation_offered": False,
                    "quick_replies": [],
                },
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "confidence": 1.0,
                "language": language,
                "sources": [],
                "resolution_state": RESOLUTION_ANSWERED,
                "quick_replies": [],
                "escalated": False,
                "escalation_offered": False,
                "ticket_id": None,
                "ticket_type": None,
            }

        if policy.is_too_short(message):
            # Very short messages need clarification before retrieval.
            answer = _short_reply(language)
            assistant_doc = _insert_message(session_name, "assistant", answer, confidence=None, sources=[])
            clarification_count = int(getattr(session_doc, "clarification_count", 0) or 0) + 1
            _update_session_state(
                session_doc,
                low_conf_count=0,
                clarification_count=clarification_count,
                last_resolution_state=RESOLUTION_NEEDS_CLARIFICATION,
                last_escalation_offered=False,
                preferred_lang=language,
            )
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=[],
                extra={
                    "language": language,
                    "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                    "escalation_offered": False,
                    "quick_replies": [],
                },
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "confidence": 0.0,
                "language": language,
                "sources": [],
                "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                "quick_replies": [],
                "escalated": False,
                "escalation_offered": False,
                "ticket_id": None,
                "ticket_type": None,
            }

        quick_reply = _match_quick_reply(message)
        issue_category = getattr(session_doc, "issue_category", "") or ""
        issue_subtype = getattr(session_doc, "issue_subtype", "") or ""
        query_for_rag = message
        skip_pre_clarify = False

        if quick_reply:
            # Quick replies map to canonical queries to improve retrieval quality.
            issue_category = quick_reply["category"]
            issue_subtype = quick_reply["subtype"]
            query_for_rag = quick_reply["canonical"]
            skip_pre_clarify = True
            _update_session_state(
                session_doc,
                issue_category=issue_category,
                issue_subtype=issue_subtype,
                last_escalation_offered=False,
                preferred_lang=language,
            )
        elif issue_subtype and _is_followup_query(message):
            query_for_rag = _expand_query_with_subtype(issue_subtype, message, language)
            skip_pre_clarify = True
        else:
            current_intent = _detect_intent(message)
            if current_intent and issue_category and current_intent != issue_category:
                issue_category = current_intent
                issue_subtype = ""
                _update_session_state(
                    session_doc,
                    issue_category=issue_category,
                    issue_subtype="",
                    last_escalation_offered=False,
                )

        intent = issue_category or _detect_intent(query_for_rag) or _detect_intent(message)
        if not skip_pre_clarify:
            # Vague intent: ask for clarification before running RAG.
            needs_clarification, intent = _needs_clarification(message)
            if needs_clarification:
                if clarification_count >= policy_settings["max_attempts"]:
                    metadata = {
                        "session_id": session_id,
                        "language": language,
                        "resolution_state": RESOLUTION_UNRESOLVED,
                        "confidence": None,
                        "top_score": None,
                    }
                    return _handle_unresolved(
                        session_id,
                        session_name,
                        session_doc,
                        history,
                        message,
                        language,
                        sources=[],
                        metadata=metadata,
                    )
                question, quick_replies = _clarify_refund_payment(language) if intent in ("refund", "payment") else (
                    _clarify_reply(language),
                    [],
                )
                previous_clarifications = clarification_count
                clarification_count = previous_clarifications + 1
                offer_allowed = previous_clarifications >= 1
                escalation_offered = bool(offer_allowed)
                assistant_doc = _insert_message(session_name, "assistant", question, confidence=0.0, sources=[])
                _update_session_state(
                    session_doc,
                    low_conf_count=prior_low_conf,
                    clarification_count=clarification_count,
                    last_resolution_state=RESOLUTION_NEEDS_CLARIFICATION,
                    issue_category=intent or issue_category,
                    last_escalation_offered=escalation_offered,
                    preferred_lang=language,
                )
                _publish_chat_message(
                    session_id,
                    assistant_doc,
                    sources=[],
                    extra={
                        "language": language,
                        "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                        "escalation_offered": escalation_offered,
                        "quick_replies": quick_replies,
                    },
                )
                return {
                    "session_id": session_id,
                    "answer": question,
                    "confidence": 0.0,
                    "language": language,
                    "sources": [],
                    "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                    "quick_replies": quick_replies,
                    "escalated": False,
                    "escalation_offered": escalation_offered,
                    "ticket_id": None,
                    "ticket_type": None,
                }

        settings = _rag_settings()
        rag_lang_hint = forced_lang or language
        rag_payload = {
            "session_id": session_id,
            "user_query": query_for_rag,
            "lang_hint": rag_lang_hint,
            "top_k": settings["top_k"],
            "history": history,
        }

        headers = {"Content-Type": "application/json"}
        if settings["rag_api_key"]:
            headers["x-api-key"] = settings["rag_api_key"]

        rag_data = None
        # Retry RAG briefly to smooth transient network errors.
        for attempt in range(3):
            try:
                rag_response = requests.post(
                    f"{settings['rag_url'].rstrip('/')}/query",
                    headers=headers,
                    json=rag_payload,
                    timeout=30,
                )
                rag_response.raise_for_status()
                rag_data = rag_response.json()
                break
            except Exception as exc:
                if attempt < 2:
                    time.sleep(1)
                    continue
                frappe.logger("ai_powered_css").warning("RAG query failed after retries: %s", exc)
                rag_data = {
                    "answer": "",
                    "confidence": 0.0,
                    "language": language,
                    "sources": [],
                }

        answer = rag_data.get("answer") or ""
        confidence = float(rag_data.get("confidence") or 0.0)
        sources = rag_data.get("sources") or []
        response_lang = rag_data.get("language") or language
        if forced_lang:
            response_lang = forced_lang
        elif language == "hi" or roman_hindi:
            response_lang = "hi"
        else:
            response_lang = "en"

        answer = _sanitize_answer(answer, response_lang)
        sources, top_score, sources_usable = _evaluate_sources(sources, policy_settings["min_top_score"])
        if not sources_usable:
            sources = []
        elif sources:
            confidence = max(confidence, top_score)

        if _is_off_topic(message) and not issue_subtype and not issue_category:
            # Off-topic queries should not be answered with unrelated KB sources.
            sources = []
            top_score = 0.0

        # Allow strong KB evidence to answer even if model self-confidence is slightly below threshold.
        answer_ready = bool(sources) and top_score >= policy_settings["answer_top_score"]
        if answer_ready and confidence < policy_settings["conf_threshold"]:
            confidence = max(confidence, top_score)
        if not answer_ready and issue_subtype and sources and top_score >= policy_settings["answer_top_score"]:
            answer_ready = True

        resolution_state = RESOLUTION_ANSWERED
        quick_replies: list[str] = []
        escalated = False
        escalation_offered = False
        ticket_id = None
        ticket_type = None

        if answer_ready:
            assistant_doc = _insert_message(session_name, "assistant", answer, confidence=confidence, sources=sources)
            _update_session_state(
                session_doc,
                low_conf_count=0,
                clarification_count=0,
                last_resolution_state=RESOLUTION_ANSWERED,
                issue_category=intent or issue_category,
                issue_subtype=issue_subtype,
                last_escalation_offered=False,
                preferred_lang=response_lang,
            )
            _publish_chat_message(
                session_id,
                assistant_doc,
                sources=sources,
                extra={
                    "language": response_lang,
                    "resolution_state": RESOLUTION_ANSWERED,
                    "escalation_offered": False,
                    "quick_replies": [],
                },
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "confidence": confidence,
                "language": response_lang,
                "sources": sources,
                "resolution_state": RESOLUTION_ANSWERED,
                "quick_replies": [],
                "escalated": False,
                "escalation_offered": False,
                "ticket_id": None,
                "ticket_type": None,
            }

        low_conf_count = prior_low_conf + 1
        very_low = confidence <= policy_settings["very_low_threshold"]
        high_risk = _is_high_risk_issue(message, intent)
        attempts = max(clarification_count, clarification_attempts)

        # Escalate only after repeated low-confidence or high-risk + no sources.
        if (very_low and not sources and high_risk) or attempts >= policy_settings["max_attempts"]:
            metadata = {
                "session_id": session_id,
                "language": response_lang,
                "resolution_state": RESOLUTION_UNRESOLVED,
                "confidence": confidence,
                "top_score": top_score if sources else None,
            }
            return _handle_unresolved(
                session_id,
                session_name,
                session_doc,
                history + [{"role": "assistant", "content": answer}],
                message,
                response_lang,
                sources=sources,
                metadata=metadata,
            )

        if intent in ("refund", "payment") and not issue_subtype:
            # Offer targeted quick replies for common refund/payment issues.
            question, quick_replies = _clarify_refund_payment(response_lang)
        elif intent in ("refund", "payment"):
            question, quick_replies = _detail_prompt(response_lang), []
        else:
            question, quick_replies = _clarify_reply(response_lang), []

        previous_clarifications = clarification_count
        clarification_count = previous_clarifications + 1
        offer_allowed = previous_clarifications >= 1 or very_low
        escalation_offered = bool(offer_allowed)
        confidence = min(confidence, 0.6)

        assistant_doc = _insert_message(session_name, "assistant", question, confidence=confidence, sources=[])
        _update_session_state(
            session_doc,
            low_conf_count=low_conf_count,
            clarification_count=clarification_count,
            last_resolution_state=RESOLUTION_NEEDS_CLARIFICATION,
            issue_category=intent or issue_category,
            issue_subtype=issue_subtype,
            last_escalation_offered=escalation_offered,
            preferred_lang=response_lang,
        )
        _publish_chat_message(
            session_id,
            assistant_doc,
            sources=[],
            extra={
                "language": response_lang,
                "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
                "escalation_offered": escalation_offered,
                "quick_replies": quick_replies,
            },
        )

        return {
            "session_id": session_id,
            "answer": question,
            "confidence": confidence,
            "language": response_lang,
            "sources": [],
            "resolution_state": RESOLUTION_NEEDS_CLARIFICATION,
            "quick_replies": quick_replies,
            "escalated": escalated,
            "escalation_offered": escalation_offered,
            "ticket_id": ticket_id,
            "ticket_type": ticket_type,
        }
    finally:
        frappe.flags.ignore_permissions = previous_ignore
        frappe.set_user(previous_user)


@frappe.whitelist(allow_guest=True)
def get_messages(session_id: str | None = None, since: str | None = None, limit: int | str = 20):
    previous_ignore = getattr(frappe.flags, "ignore_permissions", False)
    previous_user = frappe.session.user or "Guest"
    frappe.flags.ignore_permissions = True
    frappe.set_user("Administrator")
    try:
        if not session_id:
            frappe.throw(_("session_id is required"))
        session_doc = _get_session_doc(session_id)
        if not session_doc:
            return {"session_id": session_id, "messages": []}

        try:
            limit = int(limit)
        except Exception:
            limit = 20
        limit = max(1, min(limit, 50))

        filters = {"session": session_doc.name}
        if since:
            try:
                since_dt = frappe.utils.get_datetime(since)
                filters["creation"] = (">", since_dt)
            except Exception:
                pass

        rows = frappe.get_all(
            "AI CSS Chat Message",
            filters=filters,
            fields=["name", "role", "content", "confidence", "sources_json", "creation"],
            order_by="creation asc",
            limit=limit,
            ignore_permissions=True,
        )
        messages = []
        for row in rows:
            try:
                sources = json.loads(row.get("sources_json") or "[]")
            except Exception:
                sources = []
            messages.append(
                {
                    "id": row.get("name"),
                    "role": row.get("role"),
                    "content": row.get("content"),
                    "confidence": row.get("confidence"),
                    "sources": sources,
                    "created_at": row.get("creation"),
                }
            )
        return {"session_id": session_id, "messages": messages}
    finally:
        frappe.flags.ignore_permissions = previous_ignore
        frappe.set_user(previous_user)


@frappe.whitelist(allow_guest=True)
def create_ticket(
    session_id: str | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
):
    previous_ignore = getattr(frappe.flags, "ignore_permissions", False)
    previous_user = frappe.session.user or "Guest"
    frappe.flags.ignore_permissions = True
    frappe.set_user("Administrator")
    try:
        if not session_id:
            frappe.throw(_("session_id is required"))
        name, email, phone = _normalize_contact(customer_name, customer_email, customer_phone)
        session_doc = _get_session_doc(session_id)
        if not session_doc:
            frappe.throw(_("session not found"))

        allow_todo = os.getenv("ESCALATION_FALLBACK", "").lower() == "todo"
        if frappe.db.exists("DocType", "HD Ticket"):
            doctype = "HD Ticket"
        elif allow_todo:
            doctype = "ToDo"
        else:
            frappe.throw(_("Ticketing is not enabled. Ensure Helpdesk is running."))

        history = _fetch_history(session_doc.name, limit=20)
        if not name:
            name = _extract_name_from_history(history)
        subject_text = _last_user_message(session_doc.name) or "Support request"
        ticket_subject = _build_ticket_subject(subject_text)
        last_entry = _last_assistant_entry(session_doc.name)
        sources = last_entry.get("sources") or []
        confidence = last_entry.get("confidence")
        top_score = _top_score_from_sources(sources)
        metadata = {
            "session_id": session_doc.session_id,
            "language": getattr(session_doc, "preferred_lang", None) or session_doc.language,
            "resolution_state": getattr(session_doc, "last_resolution_state", None),
            "confidence": confidence,
            "top_score": top_score,
            "customer_name": name,
            "customer_email": email,
            "customer_phone": phone,
        }

        ticket_type, ticket_id = _create_ticket(
            doctype, ticket_subject, history, sources, subject_text, metadata=metadata
        )
        _update_session_state(session_doc, low_conf_count=0, last_escalation_offered=False)

        return {
            "ticket_id": ticket_id,
            "ticket_type": ticket_type,
            "customer_name": name,
            "customer_email": email,
            "customer_phone": phone,
        }
    finally:
        frappe.flags.ignore_permissions = previous_ignore
        frappe.set_user(previous_user)


@frappe.whitelist(allow_guest=True)
def get_ticket_status(ticket_id: str | None = None, include_description: str | None = None):
    previous_ignore = getattr(frappe.flags, "ignore_permissions", False)
    previous_user = frappe.session.user or "Guest"
    frappe.flags.ignore_permissions = True
    frappe.set_user("Administrator")
    try:
        if not ticket_id:
            frappe.throw(_("ticket_id is required"))

        allow_todo = os.getenv("ESCALATION_FALLBACK", "").lower() == "todo"
        if frappe.db.exists("HD Ticket", ticket_id):
            doctype = "HD Ticket"
        elif allow_todo and frappe.db.exists("ToDo", ticket_id):
            doctype = "ToDo"
        else:
            frappe.throw(_("ticket not found"))

        fields = ["subject", "status", "creation"]
        if include_description and include_description.lower() in ("1", "true", "yes"):
            fields.append("description")
        data = frappe.db.get_value(doctype, ticket_id, fields, as_dict=True) or {}
        subject = data.get("subject") or ""
        if doctype == "ToDo":
            subject = subject or "ToDo"

        response = {
            "ticket_id": ticket_id,
            "subject": subject,
            "status": data.get("status"),
            "created_at": data.get("creation"),
        }
        if "description" in data:
            response["description"] = data.get("description")
        return response
    finally:
        frappe.flags.ignore_permissions = previous_ignore
        frappe.set_user(previous_user)
