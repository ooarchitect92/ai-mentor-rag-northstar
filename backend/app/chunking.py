from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    index: int


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    lines = [line.strip() for line in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return " ".join(joined.split())


def chunk_text(text: str, chunk_size: int = 1100, overlap: int = 180) -> list[Chunk]:
    cleaned = clean_text(text)
    if not cleaned:
        return []

    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        window = cleaned[start:end]

        # Try to end at a sentence boundary for cleaner RAG context.
        if end < len(cleaned):
            sentence_end = max(window.rfind("."), window.rfind("?"), window.rfind("!"))
            if sentence_end > chunk_size * 0.55:
                end = start + sentence_end + 1
                window = cleaned[start:end]

        chunks.append(Chunk(text=window.strip(), index=idx))
        idx += 1

        if end >= len(cleaned):
            break
        start = max(0, end - overlap)

    return chunks
