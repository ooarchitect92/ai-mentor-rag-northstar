from app.chunking import chunk_text


def test_chunk_text_creates_chunks():
    text = "Sentence one. " * 200
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(c.text for c in chunks)
