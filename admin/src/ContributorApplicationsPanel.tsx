import { useEffect, useState } from "react";
import {
  approveContributorApplication,
  fetchContributorApplications,
  reinstateContributorApplication,
  rejectContributorApplication,
  suspendContributorApplication,
  type ApplicationStatus,
  type ContributorApplication,
} from "./api";
import { ConfirmModal } from "./ConfirmModal";
import {
  applicationStatusLabel,
  contributorStatusLabel,
  formatWhen,
} from "./contributorLabels";
import { ToastHost } from "./ToastHost";

type Props = {
  adminKey: string;
  onAuthFailure?: () => void;
};

type ModalState =
  | { kind: "approve" }
  | { kind: "reject" }
  | { kind: "suspend" }
  | { kind: "reinstate" }
  | null;

export function ContributorApplicationsPanel({
  adminKey,
  onAuthFailure,
}: Props) {
  const [status, setStatus] = useState<ApplicationStatus>("PENDING");
  const [items, setItems] = useState<ContributorApplication[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  const [rejectReason, setRejectReason] = useState("");

  const selected = items.find((x) => x.id === selectedId) || null;

  async function refresh(nextStatus: ApplicationStatus = status) {
    setError(null);
    try {
      const list = await fetchContributorApplications(adminKey, nextStatus);
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
    setRejectReason("");
  }

  async function confirmApprove() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await approveContributorApplication(adminKey, selected.id);
      setModal(null);
      setNotice("Contributor 신청을 승인했습니다.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "승인 실패");
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
      await rejectContributorApplication(
        adminKey,
        selected.id,
        rejectReason.trim() || undefined,
      );
      setModal(null);
      setRejectReason("");
      setNotice("Contributor 신청을 거절했습니다.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "거절 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmSuspend() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await suspendContributorApplication(
        adminKey,
        selected.id,
        rejectReason.trim() || undefined,
      );
      setModal(null);
      setRejectReason("");
      setNotice(
        "Contributor 권한을 박탈했습니다. 새 글 작성은 막고, 이미 게시된 글은 유지됩니다.",
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "박탈 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmReinstate() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await reinstateContributorApplication(adminKey, selected.id);
      setModal(null);
      setNotice("Contributor 권한을 복구했습니다.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "복구 실패");
    } finally {
      setBusy(false);
    }
  }

  const previewTitle =
    selected?.interests?.trim() ||
    selected?.motivation?.slice(0, 40) ||
    "이 신청";

  const canSuspend =
    selected?.status === "APPROVED" &&
    selected.contributor_status === "APPROVED";
  const canReinstate =
    selected?.status === "APPROVED" &&
    selected.contributor_status === "SUSPENDED";

  return (
    <>
      <ToastHost
        notice={notice}
        error={error}
        onDismissNotice={() => setNotice(null)}
        onDismissError={() => setError(null)}
      />

      <div className="tabs">
        {(["PENDING", "APPROVED", "REJECTED"] as ApplicationStatus[]).map(
          (s) => (
            <button
              key={s}
              type="button"
              className={status === s ? "is-active" : ""}
              onClick={() => setStatus(s)}
            >
              {applicationStatusLabel(s)}
            </button>
          ),
        )}
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
                  <span className="cat">
                    {contributorStatusLabel(item.contributor_status)}
                  </span>
                  <p className="title">
                    {item.interests || item.motivation.slice(0, 48) || item.id}
                  </p>
                  <p className="meta">
                    {formatWhen(item.created_at)} · {item.user_id.slice(0, 8)}…
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
            <div className="empty">왼쪽에서 신청을 선택하세요.</div>
          ) : (
            <>
              <p className="meta">
                status {selected.status} · user {selected.contributor_status} ·{" "}
                {formatWhen(selected.created_at)}
              </p>
              <span className="cat">APPLICATION</span>
              <h2>{selected.interests || "관심 주제 없음"}</h2>

              <div className="section">
                <h3>지원 동기</h3>
                <p className="prose-block">{selected.motivation}</p>
              </div>
              <div className="section">
                <h3>관심 주제</h3>
                <p className="prose-block">{selected.interests}</p>
              </div>
              {selected.sample_text?.trim() ? (
                <div className="section">
                  <h3>생각 샘플</h3>
                  <p className="prose-block">{selected.sample_text}</p>
                </div>
              ) : null}
              <div className="section">
                <h3>메타</h3>
                <p className="meta">
                  application id · {selected.id}
                  <br />
                  user id · {selected.user_id}
                  <br />
                  Contributor ·{" "}
                  {contributorStatusLabel(selected.contributor_status)}
                  <br />
                  신청일 · {formatWhen(selected.created_at)}
                  {selected.reviewed_at
                    ? ` · 검토일 · ${formatWhen(selected.reviewed_at)}`
                    : ""}
                </p>
              </div>
              {selected.admin_note ? (
                <div className="section">
                  <h3>관리자 메모</h3>
                  <p className="prose-block">{selected.admin_note}</p>
                </div>
              ) : null}

              <div className="actions">
                {selected.status === "PENDING" ? (
                  <>
                    <button
                      type="button"
                      className="primary"
                      disabled={busy}
                      onClick={() => setModal({ kind: "approve" })}
                    >
                      승인
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
                      거절
                    </button>
                  </>
                ) : null}
                {canSuspend ? (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => {
                      setRejectReason("");
                      setModal({ kind: "suspend" });
                    }}
                  >
                    권한 박탈
                  </button>
                ) : null}
                {canReinstate ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={() => setModal({ kind: "reinstate" })}
                  >
                    권한 복구
                  </button>
                ) : null}
              </div>
            </>
          )}
        </section>
      </div>

      <ConfirmModal
        open={modal?.kind === "approve"}
        title="승인할까요?"
        body={`「${previewTitle}」 신청을 승인합니다. 사용자는 Contributor로 활동할 수 있습니다.`}
        confirmLabel="승인"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmApprove()}
      />

      <ConfirmModal
        open={modal?.kind === "reject"}
        title="거절할까요?"
        body={`「${previewTitle}」 신청을 거절합니다.`}
        confirmLabel="거절"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmReject()}
      >
        <label className="modal-field">
          신청 거절 사유 (선택)
          <textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="예: 샘플이 짧아요…"
            disabled={busy}
          />
        </label>
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "suspend"}
        title="권한을 박탈할까요?"
        body={`이 사용자의 Contributor 작성 권한을 박탈합니다. 새 글·수정은 막고, 이미 게시된 깊이 있는 생각은 유지됩니다.`}
        confirmLabel="권한 박탈"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmSuspend()}
      >
        <label className="modal-field">
          박탈 사유 (선택)
          <textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="예: 반복적인 사실 오류…"
            disabled={busy}
          />
        </label>
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "reinstate"}
        title="권한을 복구할까요?"
        body={`정지된 Contributor 권한을 다시 승인합니다. 작성·제출이 가능해집니다.`}
        confirmLabel="권한 복구"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmReinstate()}
      />
    </>
  );
}
