from app.pipeline.analyze import _parse_emphasis


def test_parse_emphasis_keeps_verbatim_only():
    summary = (
        "마이크론 EPS 추정치가 약 36% 상향됐어요. "
        "다만 메모리 사이클 리스크는 있어요."
    )
    why = "AI 수요가 꺾이면 마진이 줄 수 있어요."
    raw = {
        "key_sentences": [
            "마이크론 EPS 추정치가 약 36% 상향됐어요.",
            "이 문장은 본문에 없음",
        ],
        "rise_numbers": ["36%", "99%"],
        "fall_numbers": ["36%"],  # also in rise → dropped from fall
    }
    out = _parse_emphasis(raw, summary=summary, why=why)
    assert out["key_sentences"] == ["마이크론 EPS 추정치가 약 36% 상향됐어요."]
    assert "36%" in out["rise_numbers"]
    assert "99%" not in out["rise_numbers"]
    assert out["fall_numbers"] == []
