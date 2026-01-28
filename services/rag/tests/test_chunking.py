from app.chunking import chunk_text, count_words


def test_chunking_sizes():
    text = "word " * 2200
    chunks = chunk_text(text)
    assert len(chunks) >= 2

    sizes = [count_words(c) for c in chunks]
    for size in sizes[:-1]:
        assert 500 <= size <= 1000
    assert sizes[-1] <= 1000
