from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger("rag.openai")


class EmbeddingUnavailable(Exception):
    pass


class OpenAIClient:
    def __init__(self, api_key: str, chat_model: str, embed_model: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.chat_model = chat_model
        self.embed_model = embed_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key or self.client is None:
            raise EmbeddingUnavailable("Embedding provider unavailable")
        try:
            response = self.client.embeddings.create(model=self.embed_model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.warning("OpenAI embeddings failed: %s", exc)
            raise EmbeddingUnavailable("Embedding provider unavailable") from exc

    def chat_json(self, system_prompt: str, user_prompt: str) -> tuple[str, float | None]:
        content = self._chat_raw(system_prompt, user_prompt)
        parsed = _parse_json(content)
        if not parsed:
            return content.strip(), None
        answer = str(parsed.get("answer", "")).strip() or content.strip()
        self_conf = _safe_float(parsed.get("self_confidence"))
        return answer, self_conf

    def roman_hindi_to_hi_en(self, text: str) -> dict[str, str] | None:
        if not self.api_key or self.client is None:
            raise EmbeddingUnavailable("Embedding provider unavailable")
        system_prompt = (
            "Convert the following Roman Hindi text into Hindi (Devanagari) and English. "
            "Return STRICT JSON only with keys: hi, en, language."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("OpenAI roman-hindi conversion failed: %s", exc)
            return None
        content = response.choices[0].message.content or ""
        parsed = _parse_json(content)
        if not parsed:
            return None
        return {
            "hi": str(parsed.get("hi", "")).strip(),
            "en": str(parsed.get("en", "")).strip(),
            "language": str(parsed.get("language", "hi")).strip(),
        }

    def _chat_raw(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key or self.client is None:
            raise EmbeddingUnavailable("Embedding provider unavailable")
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("OpenAI json_object response failed, retrying without response_format: %s", exc)
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
        return response.choices[0].message.content or ""


def _parse_json(content: str) -> dict[str, Any] | None:
    try:
        return json.loads(content)
    except Exception:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except Exception:
            return None
    return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None
