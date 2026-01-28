from dataclasses import dataclass
import os


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        if default is not None:
            return default
        if required:
            raise ValueError(f"{name} is required")
        return ""
    return value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_chat_model: str
    openai_embed_model: str
    qdrant_url: str
    qdrant_collection: str
    rag_api_key: str
    top_k: int
    conf_threshold: float
    max_query_chars: int


def load_settings() -> Settings:
    return Settings(
        openai_api_key=_get_env("OPENAI_API_KEY", ""),
        openai_chat_model=_get_env("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        openai_embed_model=_get_env("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        qdrant_url=_get_env("QDRANT_URL", "http://qdrant:6333"),
        qdrant_collection=_get_env("QDRANT_COLLECTION", "ai_powered_css_kb"),
        rag_api_key=_get_env("RAG_API_KEY", required=True),
        top_k=int(_get_env("TOP_K", "5")),
        conf_threshold=float(_get_env("CONF_THRESHOLD", "0.7")),
        max_query_chars=int(_get_env("MAX_QUERY_CHARS", "4000")),
    )
