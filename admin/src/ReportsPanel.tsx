import { useEffect, useState } from "react";
import {
  fetchContentReports,
  resolveContentReport,
  type ContentReport,
} from "./api";
import { ConfirmModal } from "./ConfirmModal";
import { formatWhen } from "./contributorLabels";
import { ToastHost } from "./ToastHost";

type Props = {
  adminKey: string;
  onAuthFailure?: () => void;
};

type ReportStatus = "open" | "removed" | "dismissed";

type ModalState = { kind: "remove" } | { kind: "dismiss" } | null;

const FILTERS: ReportStatus[] = ["open", "removed", "dismissed"];

const STATUS_LABEL: Record<ReportStatus, string> = {
  open: "대기",
  removed: "삭제",
  dismissed: "기각",
};

const REASON_LABEL: Record<string, string> = {
  hate: "혐오·차별",
  sexual: "음란·성적",
  violence: "폭력·위협",
  spam: "스팸",
  other: "기타",
};

function targetLabel(type: string): string {
  return type === "take" ? "깊이 있는 생각" : "댓글";
}

export function ReportsPanel({ adminKey, onAuthFailure }: Props) {
  const [status, setStatus] = useState<ReportStatus>("open");
  const [items, setItems] = useState<ContentReport[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [eject, setEject] = useState(true);
  const [modal, setModal] = useState<ModalState>(null);

  const selected = items.find((x) => x.id === selectedId) || null;

  async function refresh(nextStatus: ReportStatus = status) {
    setError(null);
    try {
      const list = await fetchContentReports(adminKey, nextStatus);
      setItems(list.items);
      if (list.items.length === 0) {
        setSelectedId(null);
        return;
      }
      const keep = list.items.find((x) => x.id === selectedId);
      setSelectedId(keep?.id || list.items[0].id);
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

  function closeModal() {
    if (busy) return;
    setModal(null);
  }

  async function confirmResolve(action: "remove" | "dismiss") {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await resolveContentReport(adminKey, selected.id, {
        action,
        eject: action === "remove" && eject,
      });
      setModal(null);
      setNotice(
        action === "remove"
          ? "콘텐츠를 내렸습니다. 24시간 대응으로 기록됩니다."
          : "신고를 기각했습니다.",
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "처리 실패");
    } finally {
      setBusy(false);
    }
  }

  const previewTitle = selected
    ? REASON_LABEL[selected.reason] || selected.reason
    : "이 신고";

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
            {STATUS_LABEL[s]}
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
                  <span className="cat">{targetLabel(item.target_type)}</span>
                  <p className="title">
                    {REASON_LABEL[item.reason] || item.reason}
                  </p>
                  <p className="meta">
                    {(item.preview || "내용 없음").slice(0, 72)}
                    <br />
                    {formatWhen(item.created_at)}
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
            <div className="empty">왼쪽에서 신고를 선택하세요.</div>
          ) : (
            <>
              <p className="meta">
                status {selected.status} · 접수 {formatWhen(selected.created_at)}
                {selected.resolved_at
                  ? ` · 처리 ${formatWhen(selected.resolved_at)}`
                  : ""}
              </p>
              <span className="cat">
                {selected.target_type === "take" ? "DEEP THOUGHT" : "COMMENT"}
              </span>
              <h2>{REASON_LABEL[selected.reason] || selected.reason}</h2>
              <p className="meta">
                24시간 안에 검토하세요. 확인되면 글을 내리고 작성자를 제한합니다.
              </p>

              <div className="section">
                <h3>내용</h3>
                <p className="prose-block">
                  {selected.preview || "미리보기가 없습니다."}
                </p>
              </div>
              {selected.details ? (
                <div className="section">
                  <h3>신고 메모</h3>
                  <p className="prose-block">{selected.details}</p>
                </div>
              ) : null}
              <div className="section">
                <h3>메타</h3>
                <p className="meta">
                  대상 · {targetLabel(selected.target_type)}
                  <br />
                  대상 id · {selected.target_id}
                  <br />
                  작성자 · {selected.target_user_id}
                  <br />
                  신고자 · {selected.reporter_id}
                </p>
              </div>

              {selected.status === "open" ? (
                <div className="actions">
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={() => {
                      setEject(true);
                      setModal({ kind: "remove" });
                    }}
                  >
                    글 내리기
                  </button>
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => setModal({ kind: "dismiss" })}
                  >
                    기각
                  </button>
                </div>
              ) : null}
            </>
          )}
        </section>
      </div>

      <ConfirmModal
        open={modal?.kind === "remove"}
        title="이 글을 내릴까요?"
        body={`「${previewTitle}」 신고 대상 글을 앱에서 내립니다.`}
        confirmLabel="내리기"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmResolve("remove")}
      >
        <label className="modal-check">
          <input
            type="checkbox"
            checked={eject}
            onChange={(e) => setEject(e.target.checked)}
            disabled={busy}
          />
          작성자도 함께 제한
        </label>
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "dismiss"}
        title="신고를 기각할까요?"
        body={`「${previewTitle}」 신고를 기각합니다. 글은 그대로 둡니다.`}
        confirmLabel="기각"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmResolve("dismiss")}
      />
    </>
  );
}
