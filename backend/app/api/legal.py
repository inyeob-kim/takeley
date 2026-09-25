"""Public legal pages for App Store / support URLs."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import get_settings

router = APIRouter(tags=["legal"])

_ACCENT = "#2D5BE3"


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} · TAKELEY</title>
  <style>
    body {{
      margin: 0;
      font-family: "Pretendard", "Apple SD Gothic Neo", system-ui, sans-serif;
      color: #111;
      background: #EEF0F3;
      line-height: 1.6;
    }}
    .shell {{
      max-width: 40rem;
      margin: 0 auto;
      min-height: 100vh;
      background: #fff;
      padding: 1.5rem 1.35rem 3rem;
    }}
    .brand {{
      margin: 0 0 1.25rem;
      font-size: 0.8125rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: {_ACCENT};
    }}
    h1 {{
      margin: 0 0 1rem;
      font-size: 1.5rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }}
    h2 {{
      margin: 1.6rem 0 0.45rem;
      font-size: 1.05rem;
      font-weight: 700;
    }}
    p, li {{ color: #333; font-size: 0.975rem; }}
    ul {{ padding-left: 1.15rem; }}
    a {{ color: {_ACCENT}; }}
    .muted {{ color: #777; font-size: 0.875rem; }}
  </style>
</head>
<body>
  <main class="shell">
    <p class="brand">TAKELEY</p>
    {body}
  </main>
</body>
</html>
"""


@router.get("/privacy", response_class=HTMLResponse)
def privacy_policy() -> HTMLResponse:
    settings = get_settings()
    origin = (settings.public_share_origin or "https://api.takeley.co").rstrip("/")
    body = f"""
    <h1>개인정보 처리방침</h1>
    <p class="muted">시행일: 2026년 9월 23일 · 운영: TAKELEY</p>
    <p>TAKELEY(테이클리)는 이슈를 짧게 읽고 의견을 남기는 모바일 앱입니다.
    이메일 회원가입 없이 기기 기준으로 이용할 수 있습니다.</p>

    <h2>1. 수집하는 정보</h2>
    <ul>
      <li>기기 식별값 (앱이 만든 익명 device ID)</li>
      <li>푸시 알림 토큰 (알림을 켠 경우, Firebase/Apple/Google)</li>
      <li>이용자가 남긴 투표, 댓글, 팔로우, 작성 글</li>
      <li>앱 버전, 플랫폼(iOS/Android)</li>
    </ul>
    <p>이름, 전화번호, 이메일은 기본으로 받지 않습니다.
    칼럼니스트가 프로필에 이메일을 공개한 경우에만 해당 정보가 노출됩니다.</p>

    <h2>2. 이용 목적</h2>
    <ul>
      <li>이슈 피드 제공 및 투표·댓글 표시</li>
      <li>새 이슈 알림 (동의한 경우)</li>
      <li>서비스 안정 운영 및 부정 이용 방지</li>
    </ul>

    <h2>3. 보관 기간</h2>
    <p>기기 세션과 이용 기록은 서비스를 쓰는 동안 보관합니다.
    앱 설정에서 <strong>내 데이터 삭제</strong>를 누르면 해당 기기와 연결된 투표, 댓글,
    알림 토큰, 세션을 삭제합니다.</p>

    <h2>4. 제3자 제공·처리위탁</h2>
    <ul>
      <li>인프라: Amazon Web Services (서울)</li>
      <li>푸시: Google Firebase Cloud Messaging, Apple Push Notification service</li>
    </ul>
    <p>광고 식별자 추적이나 제3자 광고 네트워크는 사용하지 않습니다.</p>

    <h2>5. 이용자 권리</h2>
    <p>앱 설정에서 알림을 끄거나 데이터를 삭제할 수 있습니다.
    문의는 <a href="{origin}/support">{origin}/support</a>를 이용해 주세요.</p>

    <h2>6. 연락처</h2>
    <p>운영 문의: <a href="mailto:hello@takeley.co">hello@takeley.co</a></p>
    """
    return HTMLResponse(_page("개인정보 처리방침", body))


@router.get("/support", response_class=HTMLResponse)
def support() -> HTMLResponse:
    settings = get_settings()
    origin = (settings.public_share_origin or "https://api.takeley.co").rstrip("/")
    body = f"""
    <h1>고객지원</h1>
    <p>TAKELEY는 지금 뜨는 이슈를 카드로 보고, 한 번 눌러 의견을 남기는 앱입니다.</p>
    <h2>자주 묻는 질문</h2>
    <ul>
      <li>로그인은 없습니다. 이 기기에 연결된 익명 계정으로 동작합니다.</li>
      <li>알림은 설정에서 켜고 끌 수 있습니다.</li>
      <li>내 투표·댓글·알림 토큰은 설정 → 내 데이터 삭제에서 지울 수 있습니다.</li>
    </ul>
    <h2>부적절한 활동 신고</h2>
    <p>앱에서 댓글·글을 신고하거나
    <a href="mailto:hello@takeley.co">hello@takeley.co</a>로 바로 알려 주세요.
    접수된 신고는 24시간 안에 검토하고, 문제가 확인되면 해당 글을 내리고
    해당 이용자를 제한합니다.</p>
    <h2>문의</h2>
    <p><a href="mailto:hello@takeley.co">hello@takeley.co</a></p>
    <p class="muted"><a href="{origin}/privacy">개인정보 처리방침</a>
    · <a href="{origin}/terms">이용약관</a></p>
    """
    return HTMLResponse(_page("고객지원", body))


@router.get("/data-deletion", response_class=HTMLResponse)
def data_deletion() -> HTMLResponse:
    """Play Console delete-data URL. Steps, scope, and retention must be obvious."""
    settings = get_settings()
    origin = (settings.public_share_origin or "https://api.takeley.co").rstrip("/")
    body = f"""
    <h1>데이터 삭제</h1>
    <p>TAKELEY(테이클리)에서 이 기기에 연결된 데이터를 삭제하는 방법입니다.</p>

    <h2>삭제 방법</h2>
    <ol>
      <li>TAKELEY 앱을 엽니다.</li>
      <li>아래 탭에서 <strong>프로필</strong>을 누릅니다.</li>
      <li>오른쪽 위 <strong>설정</strong> 톱니바퀴를 누릅니다.</li>
      <li><strong>내 데이터 삭제</strong>를 누르고 확인합니다.</li>
    </ol>
    <p>앱을 열 수 없으면 <a href="mailto:hello@takeley.co">hello@takeley.co</a>로
    기기에서 쓰던 닉네임을 적어 삭제를 요청해 주세요.</p>

    <h2>삭제되는 데이터</h2>
    <ul>
      <li>기기 세션과 닉네임</li>
      <li>투표, 댓글, 반응, 팔로우, 이슈를 연 기록</li>
      <li>알림 토큰과 알림 기록</li>
      <li>관심 목록과 앱 설정</li>
    </ul>
    <p>확인을 누르면 바로 삭제합니다. 그 뒤에 더 보관하지 않습니다.</p>

    <h2>남는 데이터</h2>
    <ul>
      <li>이슈 카드와 다른 사람이 남긴 글</li>
      <li>이미 공개된 칼럼 글. 계정과의 연결만 끊습니다.</li>
    </ul>

    <h2>Delete your data</h2>
    <p>Open TAKELEY, go to Profile, tap the settings gear, then tap
    <strong>내 데이터 삭제</strong> and confirm. This immediately deletes the device
    session, nickname, votes, comments, reactions, follows, view history,
    notification tokens, and app settings. Issue cards, other people's posts,
    and already published columns stay. Columns are only unlinked from the account.
    Nothing deleted is kept afterward. If you cannot open the app, email
    <a href="mailto:hello@takeley.co">hello@takeley.co</a>.</p>

    <p class="muted"><a href="{origin}/privacy">개인정보 처리방침</a></p>
    """
    return HTMLResponse(_page("데이터 삭제", body))


@router.get("/terms", response_class=HTMLResponse)
def terms_of_use() -> HTMLResponse:
    settings = get_settings()
    origin = (settings.public_share_origin or "https://api.takeley.co").rstrip("/")
    body = f"""
    <h1>이용약관</h1>
    <p class="muted">시행일: 2026년 9월 25일 · 만 18세 이상만 이용할 수 있습니다.</p>
    <p>TAKELEY(테이클리)는 이슈를 읽고 익명으로 의견·댓글·글을 남기는 서비스입니다.
    앱을 쓰려면 이 약관에 동의해야 합니다.</p>

    <h2>1. 연령</h2>
    <p>본 서비스는 만 18세 이상만 이용할 수 있습니다.</p>

    <h2>2. 금지 행위 — 무관용</h2>
    <p>혐오, 차별, 음란, 성적 착취, 폭력·위협, 괴롭힘, 스팸, 불법 콘텐츠는
    허용하지 않습니다. 위반이 확인되면 해당 글을 즉시 내리고 해당 이용자의
    이용을 제한합니다. 재발 시 영구 제한할 수 있습니다.</p>

    <h2>3. 신고·차단·숨기기</h2>
    <ul>
      <li>이용자는 부적절한 글을 신고할 수 있습니다.</li>
      <li>이용자는 다른 이용자를 차단할 수 있습니다.</li>
      <li>이용자는 원하지 않는 글을 자신의 피드에서 바로 숨길 수 있습니다.</li>
    </ul>

    <h2>4. 운영 대응 (24시간)</h2>
    <p>신고가 접수되면 운영자는 24시간 안에 검토합니다.
    문제가 확인되면 해당 콘텐츠를 삭제하고, 해당 이용자를 서비스에서
    제한(eject)합니다.</p>

    <h2>5. 연락처</h2>
    <p>부적절한 활동 신고 및 문의:
    <a href="mailto:hello@takeley.co">hello@takeley.co</a></p>

    <h2>Terms of Use (English)</h2>
    <p>TAKELEY is for users 18 and older. There is <strong>no tolerance</strong>
    for objectionable content or abusive users, including hate, sexual content,
    harassment, threats, or spam. Users can report, block, and immediately hide
    posts from their feed. We review reports within 24 hours and, when a
    violation is confirmed, remove the content and eject the user who posted it.
    Contact: <a href="mailto:hello@takeley.co">hello@takeley.co</a>.</p>

    <p class="muted"><a href="{origin}/privacy">개인정보 처리방침</a>
    · <a href="{origin}/support">고객지원</a></p>
    """
    return HTMLResponse(_page("이용약관", body))
