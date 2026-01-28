#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except Exception:
    print("ERROR: Missing dependencies. Install with: python3 -m pip install -r scripts/requirements.txt")
    raise


def load_env_file(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"')
    return env


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="infra/.env")
    parser.add_argument("--url", default="http://localhost:8001")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    env = load_env_file(Path(args.env))
    rag_key = os.getenv("RAG_API_KEY") or env.get("RAG_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY") or env.get("OPENAI_API_KEY", "")

    if not openai_key:
        print("ERROR: OPENAI_API_KEY is required for embeddings/ingest. Update infra/.env.")
        return 1
    if not rag_key:
        print("ERROR: RAG_API_KEY is required for ingest. Update infra/.env.")
        return 1

    en_files = [f for f in glob.glob("data/kb/articles/*.json") if not f.endswith(".hi.json")]
    hi_files = [f for f in glob.glob("data/kb/articles/*.hi.json")]
    files = sorted(en_files + hi_files)
    if not files:
        print("ERROR: No KB articles found. Run: make fetch-kb")
        return 1

    if args.limit:
        files = files[: args.limit]

    headers = {"Content-Type": "application/json", "x-api-key": rag_key}
    ingested = 0
    total_chunks = 0
    lang_counts: dict[str, int] = {}
    chunk_counts: dict[str, int] = {}

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        body = doc.get("body", "").strip()
        if len(body) < 200:
            continue

        lang = doc.get("lang", "en")
        ingest_doc_id = doc["doc_id"]
        if lang == "hi" and not ingest_doc_id.endswith(":hi"):
            ingest_doc_id = f"{ingest_doc_id}:hi"

        payload = {
            "doc_id": ingest_doc_id,
            "title": doc.get("title") or doc["doc_id"],
            "text": body,
            "tags": doc.get("tags", []),
            "lang": lang,
            "source_url": doc.get("source_url"),
        }

        resp = requests.post(f"{args.url}/ingest", headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"ERROR: /ingest failed for {doc['doc_id']} (HTTP {resp.status_code})")
            print(resp.text)
            if resp.status_code == 503:
                print("Hint: Embeddings unavailable. Check OPENAI_API_KEY and account quota.")
            return 1

        try:
            ingested_chunks = resp.json().get("ingested_chunks", 0)
        except Exception:
            ingested_chunks = 0

        ingested += 1
        total_chunks += ingested_chunks
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        chunk_counts[lang] = chunk_counts.get(lang, 0) + ingested_chunks
        time.sleep(0.2)

    print(f"Ingested {ingested} documents.")
    print(f"Total chunks: {total_chunks}")
    for lang, count in sorted(lang_counts.items()):
        print(f"{lang}: {count} docs, {chunk_counts.get(lang, 0)} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
