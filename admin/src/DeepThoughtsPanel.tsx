import { useEffect, useState } from "react";
import {
  fetchContributorTakes,
  fetchIssue,
  publishContributorTake,
  rejectContributorTake,
  unpublishContributorTake,
  type AdminTake,
  type TakeModStatus,
} from "./api";
import { ConfirmModal } from "./ConfirmModal";
import {
  formatWhen,
  TAKE_UNPUBLISH_RESULT,
  takeStatusLabel,
} from "./contributorLabels";
import { ToastHost } from "./ToastHost";

type Props = {
  adminKey: string;
  onAuthFailure?: () => void;
};

type ModalState =
  | { kind: "publish" }
  | { kind: "reject" }
  | { kind: "unpublish" }
  | null;

const FILTERS: TakeModStatus[] = [
  "pending_review",
  "published",
  "rejected",
];

export function DeepThoughtsPanel({ adminKey, onAuthFailure }: Props) {
  const [status, setStatus] = useState<TakeModStatus>("pending_review");
  const [items, setItems] = useState<AdminTake[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [issueTitle, setIssueTitle] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  const [rejectReason, setRejectReason] = useState("");

  const selected = items.find((x) => x.id === selectedId) || null;

  async function refresh(nextStatus: TakeModStatus = status) {
    setError(null);
    try {
      const list = await fetchContributorTakes(adminKey, nextStatus);
      setItems(list.items);
      if (list.items.length === 0) {
        setSelectedId(null);
        setIssueTitle(null);
        return;
      }
      const keep = list.items.find((x) => x.id === selectedId);
      const pick = keep?.id || list.items[0].id;
      setSelectedId(pick);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "불러오기 실패";
      setError(msg);
      if (/HTTP 401|HTTP 403|Unauthorized|Forbidden/i.test(msg)) {
        onAuthFailure?.();
      }
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adminKey, status]);

  useEffect(() => {
    if (!selected) {
      setIssueTitle(null);
      return;
    }
    let cancelled = false;
    void fetchIssue(adminKey, selected.issue_id)
      .then((issue) => {
        if (!cancelled) setIssueTitle(issue.title);
      })
      .catch(() => {
        if (!cancelled) setIssueTitle(null);
      });
    return () => {
      cancelled = true;
    };
  }, [adminKey, selected?.id, selected?.issue_id]);

  function closeModal() {
    if (busy) return;
    setModal(null);
    setRejectReason("");
  }

  async function confirmPublish() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await publishContributorTake(adminKey, selected.id);
      setModal(null);
      setNotice("깊이 있는 생각을 게시했습니다.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "게시 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmReject() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await rejectContributorTake(
        adminKey,
        selected.id,
        rejectReason.trim() || undefined,
      );
      setModal(null);
      setRejectReason("");
      setNotice("반려했습니다. 작성자가 수정할 수 있습니다.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "반려 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmUnpublish() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await unpublishContributorTake(
        adminKey,
        selected.id,
        rejectReason.trim() || undefined,
      );
      setModal(null);
      setRejectReason("");
      setNotice(
        `게시 중단 → ${takeStatusLabel(TAKE_UNPUBLISH_RESULT)} 상태로 바꿨습니다.`,
      );
      setStatus(TAKE_UNPUBLISH_RESULT);
      await refresh(TAKE_UNPUBLISH_RESULT);
    } catch (err) {
      setError(err instanceof Error ? err.message : "게시 중단 실패");
    } finally {
      setBusy(false);
    }
  }

  const takeTitle = selected?.title?.trim() || "이 생각";

  return (
    <>
      <ToastHost
        notice={notice}
        error={error}
        onDismissNotice={() => setNotice(null)}
        onDismissError={() => setError(null)}
      />

      <div className="tabs">
        {FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            className={status === s ? "is-active" : ""}
            onClick={() => setStatus(s)}
          >
            {takeStatusLabel(s)}
          </button>
        ))}
      </div>

      <div className="layout">
        <aside className="panel">
          <ul className="list">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={selectedId === item.id ? "is-selected" : ""}
                  onClick={() => setSelectedId(item.id)}
                >
                  <span className="cat">{takeStatusLabel(item.status)}</span>
                  <p className="title">{item.title}</p>
                  <p className="meta">
                    {item.display_name || item.author_id.slice(0, 8)} · 조회{" "}
                    {item.view_count} · 공감 {item.reaction_count}
                    <br />
                    {formatWhen(item.updated_at)}
                  </p>
                </button>
              </li>
            ))}
            {items.length === 0 ? (
              <li>
                <button type="button" disabled>
                  <p className="title">항목이 없어요</p>
                </button>
              </li>
            ) : null}
          </ul>
        </aside>

        <section className="panel detail">
          {!selected ? (
            <div className="empty">왼쪽에서 생각을 선택하세요.</div>
          ) : (
            <>
              <p className="meta">
                status {selected.status} · 작성 {formatWhen(selected.created_at)}{" "}
                · 수정 {formatWhen(selected.updated_at)}
                {selected.published_at
                  ? ` · 게시 ${formatWhen(selected.published_at)}`
                  : ""}
              </p>
              <span className="cat">DEEP THOUGHT</span>
              <p className="meta">
                이슈 · {issueTitle || selected.issue_id}
              </p>
              <h2>{selected.title}</h2>
              <p className="meta">
                {selected.display_name || "이름 없음"} · {selected.author_id}
              </p>

              <div className="section">
                <h3>본문</h3>
                <div className="column">
                  {selected.body
                    .split(/\n\s*\n/)
                    .map((p) => p.trim())
                    .filter(Boolean)
                    .map((p, i) => (
                      <p key={`${i}-${p.slice(0, 24)}`}>{p}</p>
                    ))}
                  {!selected.body.trim() ? (
                    <p className="meta">본문이 비어 있어요.</p>
                  ) : null}
                </div>
              </div>

              {(selected.source_urls || []).length > 0 ? (
                <div className="section">
                  <h3>출처</h3>
                  <ul className="source-url-list">
                    {selected.source_urls.map((url) => (
                      <li key={url}>
                        <a href={url} target="_blank" rel="noreferrer">
                          {url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="section">
                <h3>지표</h3>
                <p className="meta">
                  조회 {selected.view_count.toLocaleString("ko-KR")} · 공감{" "}
                  {selected.reaction_count.toLocaleString("ko-KR")}
                </p>
              </div>

              {selected.admin_note ? (
                <div className="section">
                  <h3>관리자 메모</h3>
                  <p className="prose-block">{selected.admin_note}</p>
                </div>
              ) : null}

              <div className="actions">
                {selected.status === "pending_review" ? (
                  <>
                    <button
                      type="button"
                      className="primary"
                      disabled={busy}
                      onClick={() => setModal({ kind: "publish" })}
                    >
                      게시
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={() => {
                        setRejectReason("");
                        setModal({ kind: "reject" });
                      }}
                    >
                      반려
                    </button>
                  </>
                ) : null}
                {selected.status === "published" ? (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => {
                      setRejectReason("");
                      setModal({ kind: "unpublish" });
                    }}
                  >
                    게시 중단
                  </button>
                ) : null}
              </div>
            </>
          )}
        </section>
      </div>

      <ConfirmModal
        open={modal?.kind === "publish"}
        title="게시할까요?"
        body={`「${takeTitle}」를 앱 이슈 상세에 공개합니다.`}
        confirmLabel="게시"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmPublish()}
      />

      <ConfirmModal
        open={modal?.kind === "reject"}
        title="반려할까요?"
        body={`「${takeTitle}」를 반려합니다. 작성자가 수정 후 다시 제출할 수 있습니다.`}
        confirmLabel="반려"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmReject()}
      >
        <label className="modal-field">
          검토 의견 (선택)
          <textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="예: 사실 확인이 더 필요해요…"
            disabled={busy}
          />
        </label>
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "unpublish"}
        title="게시를 중단할까요?"
        body={`「${takeTitle}」를 앱에서 내리고 ${takeStatusLabel(TAKE_UNPUBLISH_RESULT)} 상태로 바꿉니다.`}
        confirmLabel="게시 중단"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmUnpublish()}
      >
        <label className="modal-field">
          사유 (선택)
          <textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="예: 사실 오류 확인…"
            disabled={busy}
          />
        </label>
      </ConfirmModal>
    </>
  );
}
