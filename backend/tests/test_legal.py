from app.api.legal import data_deletion, privacy_policy, support, terms_of_use


def test_privacy_and_support_pages():
    privacy = privacy_policy()
    assert privacy.status_code == 200
    assert "개인정보 처리방침" in privacy.body.decode()
    assert "내 데이터 삭제" in privacy.body.decode()

    page = support()
    assert page.status_code == 200
    assert "고객지원" in page.body.decode()
    assert "hello@takeley.co" in page.body.decode()

    deletion = data_deletion()
    text = deletion.body.decode()
    assert deletion.status_code == 200
    assert "데이터 삭제" in text
    assert "내 데이터 삭제" in text
    assert "TAKELEY" in text

    terms = terms_of_use()
    terms_text = terms.body.decode()
    assert terms.status_code == 200
    assert "이용약관" in terms_text
    assert "18" in terms_text
    assert "24시간" in terms_text
    assert "no tolerance" in terms_text.lower()
    assert "hello@takeley.co" in terms_text
