from app.pipeline.tts import _chunk_transcript


def test_chunk_keeps_short_text():
    text = "짧은 브리핑입니다."
    assert _chunk_transcript(text) == [text]


def test_chunk_splits_long_paragraphs():
    para = "가" * 5000
    chunks = _chunk_transcript(para)
    assert len(chunks) >= 2
    assert all(len(c) <= 3800 for c in chunks)
