from __future__ import annotations

import logging
import time
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .chunking import chunk_text
from .config import Settings, load_settings
from .confidence import compute_confidence
from .openai_client import EmbeddingUnavailable, OpenAIClient
from .qdrant_store import QdrantStore, VectorStoreUnavailable, build_point
from .rag import build_system_prompt, build_user_prompt, detect_language, detect_roman_hindi, fallback_answer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("rag")

app = FastAPI(title="RAG Service", version="0.2.0")


class IngestRequest(BaseModel):
    doc_id: str
    title: str
    text: str
    tags: list[str] = Field(default_factory=list)
    lang: Literal["en", "hi"]
    source_url: str | None = None


class IngestResponse(BaseModel):
    ingested_chunks: int
    doc_id: str


class QueryRequest(BaseModel):
    session_id: str
    user_query: str
    lang_hint: Literal["en", "hi"] | None = None
    top_k: int | None = None
    history: list[dict] | None = None


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    language: Literal["en", "hi"]
    sources: list[dict]
    retrieved_k: int


def safe_query_response(language: str) -> QueryResponse:
    if language == "hi":
        answer = "मुझे नॉलेज बेस से पुष्टि नहीं मिल पाई। मैं यहां सपोर्ट टिकट बना सकता हूँ।"
    else:
        answer = "I couldn't confirm this from the knowledge base. I can create a support ticket for you here."
    return QueryResponse(
        answer=answer,
        confidence=0.0,
        language=language,
        sources=[],
        retrieved_k=0,
    )


@app.on_event("startup")
def on_startup() -> None:
    settings = load_settings()
    app.state.settings = settings
    app.state.openai = OpenAIClient(
        api_key=settings.openai_api_key,
        chat_model=settings.openai_chat_model,
        embed_model=settings.openai_embed_model,
    )
    app.state.qdrant = QdrantStore(url=settings.qdrant_url, collection=settings.qdrant_collection)
    logger.info("RAG service started")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_openai(request: Request) -> OpenAIClient:
    return request.app.state.openai


def get_qdrant(request: Request) -> QdrantStore:
    return request.app.state.qdrant


def require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> None:
    if not x_api_key or x_api_key != settings.rag_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["x-request-id"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s latency_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
def ingest(
    payload: IngestRequest,
    settings: Settings = Depends(get_settings),
    client: OpenAIClient = Depends(get_openai),
    store: QdrantStore = Depends(get_qdrant),
):
    chunks = chunk_text(payload.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Empty document")

    try:
        embeddings = client.embed_texts(chunks)
        store.ensure_collection(vector_size=len(embeddings[0]))
    except EmbeddingUnavailable:
        raise HTTPException(status_code=503, detail="Embedding provider unavailable")
    except VectorStoreUnavailable:
        raise HTTPException(status_code=503, detail="Vector store unavailable")

    points = []
    for index, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{payload.doc_id}#{index}"
        point = build_point(
            chunk_id=chunk_id,
            vector=vector,
            doc_id=payload.doc_id,
            title=payload.title,
            tags=payload.tags,
            lang=payload.lang,
            chunk_text=chunk,
            source_url=payload.source_url,
        )
        points.append(point)

    try:
        store.upsert_chunks(points)
    except VectorStoreUnavailable:
        raise HTTPException(status_code=503, detail="Vector store unavailable")
    return IngestResponse(ingested_chunks=len(points), doc_id=payload.doc_id)


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
def query(
    payload: QueryRequest,
    settings: Settings = Depends(get_settings),
    client: OpenAIClient = Depends(get_openai),
    store: QdrantStore = Depends(get_qdrant),
):
    user_query = payload.user_query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Empty query")

    roman_hindi = detect_roman_hindi(user_query)
    language = payload.lang_hint or detect_language(user_query)
    if payload.lang_hint == "en":
        roman_hindi = False
    if roman_hindi:
        language = "hi"

    if len(user_query) > settings.max_query_chars:
        logger.warning("Query truncated from %s to %s chars", len(user_query), settings.max_query_chars)
        user_query = user_query[: settings.max_query_chars]

    candidate_texts: list[str] = []
    user_query_for_prompt = user_query
    if roman_hindi:
        try:
            converted = client.roman_hindi_to_hi_en(user_query)
            if converted:
                hi_text = converted.get("hi") or ""
                en_text = converted.get("en") or ""
                if hi_text:
                    candidate_texts.append(hi_text)
                    user_query_for_prompt = hi_text
                if en_text:
                    candidate_texts.append(en_text)
        except EmbeddingUnavailable:
            return safe_query_response(language)

    candidate_texts.append(user_query)
    unique_texts = []
    for text in candidate_texts:
        if text and text not in unique_texts:
            unique_texts.append(text)

    try:
        vectors = client.embed_texts(unique_texts)
    except EmbeddingUnavailable:
        return safe_query_response(language)

    top_k = payload.top_k or settings.top_k
    try:
        best_results: list[dict] = []
        best_score = -1.0
        for vector in vectors:
            results = store.search(query_vector=vector, top_k=top_k)
            score = results[0]["score"] if results else 0.0
            if score > best_score:
                best_score = score
                best_results = results
        results = best_results
    except VectorStoreUnavailable:
        return safe_query_response(language)

    system_prompt = build_system_prompt(language)
    user_prompt = build_user_prompt(user_query_for_prompt, results, payload.history or [])
    try:
        answer, self_confidence = client.chat_json(system_prompt, user_prompt)
    except Exception as exc:
        logger.warning("OpenAI chat failed, using fallback answer: %s", exc)
        answer, self_confidence = fallback_answer(language, results)

    top_score = results[0]["score"] if results else 0.0
    confidence = compute_confidence(top_score, self_confidence)

    sources = []
    for item in results:
        payload_data = item.get("payload", {})
        sources.append(
            {
                "chunk_id": payload_data.get("chunk_id", item.get("id")),
                "doc_id": payload_data.get("doc_id"),
                "title": payload_data.get("title"),
                "source_url": payload_data.get("source_url"),
                "score": item.get("score"),
            }
        )

    return QueryResponse(
        answer=answer,
        confidence=confidence,
        language=language,
        sources=sources,
        retrieved_k=len(results),
    )
