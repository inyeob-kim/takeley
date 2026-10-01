from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import (
    ClosuresOut,
    IssueCommentIn,
    IssueCommentListOut,
    IssueCommentOut,
    IssueEventIn,
    IssueEventOut,
    IssueListOut,
    IssueOut,
    IssueParticipateIn,
    IssueParticipateOut,
    JudgmentLogOut,
    MyActivityOut,
    OtherTakeActionIn,
    OtherTakeMaybeOut,
    OtherTakeOut,
    RecapTodayOut,
)
from app.services.issue_service import IssueService
from app.services.judgment_log_service import JudgmentLogService
from app.services.other_take_service import mark_other_take, pick_other_take

router = APIRouter(prefix="/issues", tags=["issues"])


def _uid(user_id: str | None) -> str:
    return user_id or get_settings().default_user_id


@router.get("", response_model=IssueListOut)
def list_issues(
    limit: int = Query(20, ge=1, le=50),
    sort: str = Query("trending", pattern="^(trending|rising|new)$"),
    category: str | None = Query(
        None,
        description="Industry filter: 정치|경제|금융|기술|AI|사회|국제|문화|스포츠|엔터",
    ),
    content_kind: str = Query(
        "ISSUE",
        pattern="^(ISSUE|NEWS|ALL)$",
        description="ISSUE (default home) | NEWS | ALL",
    ),
    q: str | None = Query(
        None,
        max_length=40,
        description="Search title / summary / why_it_matters",
    ),
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueListOut:
    return IssueService(db).list_issues(
        limit=limit,
        sort=sort,
        category=category,
        content_kind=content_kind,
        q=q,
        user_id=_uid(user_id),
    )


@router.get("/activity/me", response_model=MyActivityOut)
def my_activity(
    user_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> MyActivityOut:
    return IssueService(db).my_activity(_uid(user_id), limit=limit)


@router.get("/judgments/me", response_model=JudgmentLogOut)
def my_judgments(
    user_id: str | None = Query(None),
    limit: int = Query(40, ge=1, le=50),
    db: Session = Depends(get_db),
) -> JudgmentLogOut:
    raw = JudgmentLogService(db).list_judgments(_uid(user_id), limit=limit)
    return JudgmentLogOut.model_validate(raw)


@router.get("/recap/today", response_model=RecapTodayOut)
def recap_today(
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> RecapTodayOut:
    raw = JudgmentLogService(db).recap_today(_uid(user_id))
    return RecapTodayOut.model_validate(raw)


@router.get("/closures/me", response_model=ClosuresOut)
def my_closures(
    user_id: str | None = Query(None),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
) -> ClosuresOut:
    raw = JudgmentLogService(db).closures_me(_uid(user_id), limit=limit)
    return ClosuresOut.model_validate(raw)


@router.get("/{issue_id}", response_model=IssueOut)
def get_issue(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueOut:
    out = IssueService(db).get_issue(issue_id, user_id=_uid(user_id))
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/follow", response_model=IssueOut)
def follow_issue(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueOut:
    out = IssueService(db).follow(issue_id, user_id=_uid(user_id))
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.delete("/{issue_id}/follow", response_model=IssueOut)
def unfollow_issue(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueOut:
    out = IssueService(db).unfollow(issue_id, user_id=_uid(user_id))
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/view", response_model=IssueOut)
def view_issue(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueOut:
    out = IssueService(db).record_view(issue_id, user_id=_uid(user_id))
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/participate", response_model=IssueParticipateOut)
def participate(
    issue_id: str,
    body: IssueParticipateIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueParticipateOut:
    uid = _uid(body.user_id or user_id)
    try:
        result = IssueService(db).participate(
            issue_id,
            user_id=uid,
            option_id=body.option_id,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found or not votable")
    return IssueParticipateOut(**result)


@router.get("/{issue_id}/other-take", response_model=OtherTakeMaybeOut)
def get_other_take(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> OtherTakeMaybeOut:
    card = pick_other_take(db, issue_id=issue_id, user_id=_uid(user_id))
    if not card:
        return OtherTakeMaybeOut(item=None)
    return OtherTakeMaybeOut(item=OtherTakeOut(**card))


@router.post("/{issue_id}/other-take/skip")
def skip_other_take(
    issue_id: str,
    body: OtherTakeActionIn | None = None,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    body = body or OtherTakeActionIn()
    uid = _uid(body.user_id or user_id)
    ok = mark_other_take(
        db,
        issue_id=issue_id,
        user_id=uid,
        action="skip",
        exposure_id=body.exposure_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="exposure_not_found")
    return {"ok": True}


@router.post("/{issue_id}/other-take/open")
def open_other_take(
    issue_id: str,
    body: OtherTakeActionIn | None = None,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    body = body or OtherTakeActionIn()
    uid = _uid(body.user_id or user_id)
    ok = mark_other_take(
        db,
        issue_id=issue_id,
        user_id=uid,
        action="open",
        exposure_id=body.exposure_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="exposure_not_found")
    return {"ok": True}


@router.get("/{issue_id}/comments", response_model=IssueCommentListOut)
def list_comments(
    issue_id: str,
    limit: int = Query(50, ge=1, le=100),
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueCommentListOut:
    items = IssueService(db).list_comments(issue_id, user_id=user_id, limit=limit)
    return IssueCommentListOut(items=items, count=len(items))


@router.post("/{issue_id}/comments", response_model=IssueCommentOut)
def add_comment(
    issue_id: str,
    body: IssueCommentIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueCommentOut:
    uid = _uid(body.user_id or user_id)
    try:
        out = IssueService(db).add_comment(issue_id, user_id=uid, content=body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="Issue not found")
    return out


@router.post("/{issue_id}/events", response_model=IssueEventOut)
def record_event(
    issue_id: str,
    body: IssueEventIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> IssueEventOut:
    uid = body.user_id or user_id
    # impression: anonymous OK; other events need a user id (default_user_id).
    resolved = None if body.event == "impression" and not uid else _uid(uid)
    result = IssueService(db).record_event(
        issue_id,
        body.event,
        user_id=resolved,
        share_id=body.share_id,
        ref_user_id=body.ref_user_id,
        share_intent=body.share_intent,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueEventOut(**result)
