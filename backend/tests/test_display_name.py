from app.services.display_name import normalize_display_name


def test_normalize_display_name_blank_clears():
    assert normalize_display_name(None) is None
    assert normalize_display_name("") is None
    assert normalize_display_name("   ") is None


def test_normalize_display_name_ok():
    assert normalize_display_name("테이크") == "테이크"
    assert normalize_display_name("  ab  ") == "ab"
    assert normalize_display_name("abcdefghijklmnop") == "abcdefghijklmnop"


def test_normalize_display_name_rejects_length_and_breaks():
    try:
        normalize_display_name("a")
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        normalize_display_name("abcdefghijklmnopq")
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        normalize_display_name("줄\n바꿈")
        assert False, "expected ValueError"
    except ValueError:
        pass
