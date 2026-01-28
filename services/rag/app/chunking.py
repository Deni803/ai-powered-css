from __future__ import annotations

from typing import Iterable


# Word-based chunking as a token approximation. In practice, ~1 word ~= 1 token
# for English/Hindi mixed text, so we target 800 words with overlap to keep
# chunks within ~500-1000 tokens.

def chunk_text(
    text: str,
    min_words: int = 500,
    max_words: int = 1000,
    target_words: int = 800,
    overlap: int = 80,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    if len(words) <= max_words:
        return [" ".join(words).strip()]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words).strip())
        if end == len(words):
            break
        start = max(0, end - overlap)

    # Merge a tiny trailing chunk into the previous one (keep <= max_words).
    if len(chunks) >= 2:
        last_words = chunks[-1].split()
        if len(last_words) < min_words:
            prev_words = chunks[-2].split()
            merged = prev_words + last_words
            if len(merged) <= max_words:
                chunks[-2] = " ".join(merged).strip()
                chunks.pop()

    return [c for c in chunks if c]


def count_words(text: str) -> int:
    return len(text.split())
