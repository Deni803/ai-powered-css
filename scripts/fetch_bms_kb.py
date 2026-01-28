#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import requests
    from bs4 import BeautifulSoup
except Exception as exc:  # pragma: no cover
    print("ERROR: Missing dependencies. Install with: python3 -m pip install -r scripts/requirements.txt")
    raise

ALLOWED_DOMAINS = {"support.bookmyshow.com", "in.bookmyshow.com"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
RATE_LIMIT_SECONDS = 1.0

RAW_DIR = Path("data/kb/raw")
ARTICLE_DIR = Path("data/kb/articles")


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query = parsed.query
    return urlunparse((scheme, netloc, path, "", query, ""))


def is_allowed(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return False
    return netloc in ALLOWED_DOMAINS


def is_kb_related(url: str) -> bool:
    path = urlparse(url).path.lower()
    return (
        "/support/solutions" in path
        or "/help-centre" in path
        or "/help-center" in path
    )


def is_article_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    patterns = [
        "/support/solutions/articles/",
        "/support/solutions/article/",
        "/help-centre/article/",
        "/help-centre/articles/",
    ]
    return any(p in path for p in patterns)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "doc"


def stable_doc_id(url: str, title: str) -> str:
    slug = slugify(title) if title else slugify(urlparse(url).path.split("/")[-1])
    short = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"bms-{slug}-{short}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_raw(url: str, html: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    filename = hashlib.sha256(url.encode("utf-8")).hexdigest() + ".html"
    path = RAW_DIR / filename
    if not path.exists():
        path.write_text(html, encoding="utf-8")
    return path


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return ""


def extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(
        ["script", "style", "noscript", "header", "footer", "nav", "form", "button", "input", "svg", "canvas", "iframe"]
    ):
        tag.decompose()

    for selector in [
        ".breadcrumb",
        ".breadcrumbs",
        ".related",
        ".recommended",
        ".feedback",
        ".helpful",
        ".sidebar",
        ".search",
        ".article-footer",
        ".article__footer",
        ".article__header",
        ".solution-footer",
        ".share",
        ".social",
        ".print",
        ".pagination",
        ".pager",
    ]:
        for node in soup.select(selector):
            node.decompose()

    for selector in [
        ".article-body",
        ".article__content",
        ".article-content",
        ".content-body",
        ".kb-article",
        ".solution-article",
        ".solutions-article",
        "article",
        "main",
        ".content",
        ".help-center",
    ]:
        for node in soup.select(selector):
            text = node.get_text("\n", strip=True)
            if len(text) > 200:
                return clean_text(text)

    body = soup.body
    if body:
        return clean_text(body.get_text("\n", strip=True))

    return clean_text(soup.get_text("\n", strip=True))


def clean_text(text: str) -> str:
    strip_patterns = [
        r"solution home",
        r"recommended topics",
        r"did you find it helpful\??",
        r"send feedback",
        r"help us improve.*",
        r"sorry we couldn.?t be helpful.*",
        r"modified on:\s*[a-z0-9,\s:]+",
        r"updated on:\s*[a-z0-9,\s:]+",
        r"\bprint\b",
        r"\bfaq'?s?\b",
        r"powered by freshdesk",
        r"\bback to top\b",
        r"\bsubmit a request\b",
    ]
    strip_compiled = [re.compile(p, re.IGNORECASE) for p in strip_patterns]

    skip_patterns = [
        r"^home\s*/",
        r"^yes$",
        r"^no$",
        r"^search$",
        r"^share$",
    ]
    skip_compiled = [re.compile(p, re.IGNORECASE) for p in skip_patterns]

    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    seen = set()
    for line in lines:
        if not line or len(line) <= 2:
            continue
        for pattern in strip_compiled:
            line = pattern.sub("", line)
        line = re.sub(r"\s{2,}", " ", line).strip(" -|")
        if not line or len(line) <= 2:
            continue
        if any(p.search(line) for p in skip_compiled):
            continue
        if "BookMyShow Support Centre" in line and len(line) < 60:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)

    merged = "\n".join(cleaned)
    merged = re.sub(r"[ \t]+", " ", merged)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()


def discover_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if is_allowed(absolute) and is_kb_related(absolute):
            links.append(absolute)
    return links


def fetch_url(session: requests.Session, url: str, retries: int = 3) -> str:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=(10, 20))
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            return resp.text
        except Exception as exc:
            if attempt == retries:
                raise
            time.sleep(1.5 * attempt)
    return ""


def load_seeds(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    seeds = data.get("seeds", data if isinstance(data, list) else [])
    return [normalize_url(s) for s in seeds]


def write_article(doc: dict, force: bool) -> bool:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    doc_path = ARTICLE_DIR / f"{doc['doc_id']}.json"
    if doc_path.exists() and not force:
        existing = json.loads(doc_path.read_text(encoding="utf-8"))
        if existing.get("content_hash") == doc.get("content_hash"):
            return False
    doc_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def translate_to_hindi(docs: list[dict], top_n_categories: int, force: bool) -> None:
    if os.getenv("KB_TRANSLATE_HI", "").lower() != "true":
        return

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("WARN: KB_TRANSLATE_HI=true but OPENAI_API_KEY is missing; skipping translation")
        return

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    category_counts: dict[str, int] = {}
    for doc in docs:
        category = doc.get("category") or "Uncategorized"
        category_counts[category] = category_counts.get(category, 0) + 1

    top_categories = {k for k, _ in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:top_n_categories]}

    for doc in docs:
        category = doc.get("category") or "Uncategorized"
        if category not in top_categories:
            continue

        hi_path = ARTICLE_DIR / f"{doc['doc_id']}.hi.json"
        if hi_path.exists() and not force:
            continue

        prompt = (
            "Translate the following support article text to Hindi. "
            "Do not summarize or add new information. Output only the Hindi translation.\n\n"
            f"TEXT:\n{doc['body']}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional English-to-Hindi translator."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        translated = response.choices[0].message.content or ""

        hi_doc = {
            **doc,
            "lang": "hi",
            "translated_from": doc["doc_id"],
            "translation_model": model,
            "body": translated.strip(),
            "content_hash": content_hash(translated.strip()),
        }
        hi_path.write_text(json.dumps(hi_doc, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="data/kb/sources/bookmyshow_seeds.json")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=int(os.getenv("KB_MAX_PAGES", "250")),
        help="Limit total seed pages fetched",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=int(os.getenv("KB_MAX_ARTICLES", "120")),
        help="Limit total articles parsed",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=int(os.getenv("KB_MAX_DEPTH", "3")),
        help="Max crawl depth",
    )
    args = parser.parse_args()

    seeds_path = Path(args.seeds)
    seeds = load_seeds(seeds_path)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    to_visit: list[tuple[str, int]] = [(seed, 0) for seed in seeds]
    visited: set[str] = set()
    article_urls: set[str] = set()
    category_hint: dict[str, str] = {}
    discovered_urls: list[str] = []
    blocked_urls: list[dict] = []
    low_quality = 0
    saved_count = 0
    skipped_count = 0

    fetched_pages = 0

    while to_visit:
        url, depth = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        discovered_urls.append(url)

        if args.max_pages and fetched_pages >= args.max_pages:
            break

        print(f"Fetching: {url}")
        try:
            html = fetch_url(session, url)
        except Exception as exc:
            reason = str(exc)
            print(f"WARN: Failed to fetch {url}: {reason}")
            blocked_urls.append(
                {
                    "url": url,
                    "status": reason,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            continue

        fetched_pages += 1
        save_raw(url, html)
        soup = BeautifulSoup(html, "html.parser")
        title = extract_title(soup)
        base_category = title.strip() if title else None

        for link in discover_links(soup, url):
            if link not in visited and depth + 1 <= args.max_depth:
                to_visit.append((link, depth + 1))
            if is_article_url(link):
                article_urls.add(link)
                if base_category and link not in category_hint:
                    category_hint[link] = base_category

        time.sleep(RATE_LIMIT_SECONDS)

    docs: list[dict] = []
    for article_url in sorted(article_urls):
        if args.max_articles and len(docs) >= args.max_articles:
            break
        print(f"Parsing article: {article_url}")
        try:
            html = fetch_url(session, article_url)
        except Exception as exc:
            print(f"WARN: Failed to fetch article {article_url}: {exc}")
            continue

        save_raw(article_url, html)
        soup = BeautifulSoup(html, "html.parser")
        title = extract_title(soup)
        body = extract_text(soup)
        if not body or len(body) < 200:
            low_quality += 1
            continue

        doc_id = stable_doc_id(article_url, title)
        doc = {
            "doc_id": doc_id,
            "title": title or doc_id,
            "category": category_hint.get(article_url) or "Uncategorized",
            "tags": [],
            "lang": "en",
            "source_url": article_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash(body),
            "body": body,
        }
        updated = write_article(doc, force=args.force)
        if updated:
            print(f"Saved: {doc_id}")
            saved_count += 1
        else:
            skipped_count += 1
        docs.append(doc)
        time.sleep(RATE_LIMIT_SECONDS)

    translate_to_hindi(docs, top_n_categories=20, force=args.force)

    Path("data/kb/sources").mkdir(parents=True, exist_ok=True)
    (Path("data/kb/sources") / "discovered_urls.json").write_text(
        json.dumps(sorted(set(discovered_urls)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (Path("data/kb/sources") / "blocked_urls.json").write_text(
        json.dumps(blocked_urls, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    en_count = len([p for p in ARTICLE_DIR.glob("*.json") if not p.name.endswith(".hi.json")])
    hi_count = len(list(ARTICLE_DIR.glob("*.hi.json")))

    print(f"Completed. Articles discovered: {len(article_urls)}")
    print(f"Saved: {saved_count}, Skipped (unchanged): {skipped_count}, Low quality: {low_quality}")
    print(f"Total on disk: {en_count} EN, {hi_count} HI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
