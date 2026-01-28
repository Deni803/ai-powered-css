#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from openai import OpenAI
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
    args = parser.parse_args()

    env = load_env_file(Path(args.env))

    def get_env(key: str, default: str = "") -> str:
        return os.getenv(key) or env.get(key, default)

    if get_env("KB_TRANSLATE_HI", "").lower() != "true":
        print("KB_TRANSLATE_HI is not true; skipping translation.")
        return 0

    api_key = get_env("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is required for translation. Update infra/.env.")
        return 1

    max_items = int(get_env("KB_TRANSLATE_MAX", "30"))
    categories_filter = get_env("KB_TRANSLATE_CATEGORIES", "").strip()
    allowed_categories = {c.strip() for c in categories_filter.split(",") if c.strip()}

    model = get_env("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    files = [f for f in glob.glob("data/kb/articles/*.json") if not f.endswith(".hi.json")]
    if not files:
        print("ERROR: No KB articles found. Run: make fetch-kb")
        return 1

    translated = 0
    for path in sorted(files):
        if translated >= max_items:
            break

        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        if allowed_categories and doc.get("category") not in allowed_categories:
            continue

        hi_path = Path("data/kb/articles") / f"{doc['doc_id']}.hi.json"
        if hi_path.exists():
            continue

        body = doc.get("body", "").strip()
        if len(body) < 200:
            continue

        prompt = (
            "Translate the following support article text to Hindi. "
            "Do not summarize or add any information. Output only the Hindi translation.\n\n"
            f"TEXT:\n{body}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional English-to-Hindi translator."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        translated_body = (response.choices[0].message.content or "").strip()

        hi_doc = {
            **doc,
            "lang": "hi",
            "translated_from": doc["doc_id"],
            "translation_model": model,
            "translation_at": datetime.now(timezone.utc).isoformat(),
            "body": translated_body,
        }
        hi_path.write_text(json.dumps(hi_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        translated += 1

    print(f"Translated {translated} articles to Hindi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
