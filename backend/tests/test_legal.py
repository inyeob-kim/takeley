from app.api.legal import data_deletion, privacy_policy, support


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
