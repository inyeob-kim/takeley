import { useEffect, useState } from "react";
import {
  createIssue,
  fetchCounts,
  fetchColumnists,
  fetchIssue,
  fetchIssues,
  publishIssue,
  rejectIssue,
  resolveMediaUrl,
  unpublishIssue,
  updateIssue,
  uploadIssueImage,
  type AdminColumnist,
  type AdminIssue,
  type AdminIssueUpdate,
  type Counts,
  type IssueStatus,
} from "./api";
import { ConfirmModal } from "./ConfirmModal";
import { ColumnEditor } from "./ColumnEditor";
import { ColumnistsPanel } from "./ColumnistsPanel";
import { ContributorApplicationsPanel } from "./ContributorApplicationsPanel";
import { DeepThoughtsPanel } from "./DeepThoughtsPanel";
import { ToastHost } from "./ToastHost";
import { ADMIN_KEY_STORAGE } from "./config";

const CATEGORIES = [
  "정치",
  "경제",
  "금융",
  "기술",
  "AI",
  "사회",
  "국제",
  "문화",
  "스포츠",
  "엔터",
] as const;

type AdminSection = "issues" | "columnists" | "applications" | "takes";

type EditForm = {
  title: string;
  summary: string;
  why_it_matters: string;
  column_body: string;
  column_author_name: string;
  column_author_image_url: string;
  columnist_id: string;
  image_url: string;
  key_points_text: string;
  category: string;
  participation_suitable: boolean;
  participation_question: string;
  participation_options_text: string;
  show_sources: boolean;
  push_title: string;
  push_body: string;
};

type ModalState =
  | { kind: "publish" }
  | { kind: "reject" }
  | { kind: "unpublish" }
  | { kind: "discard-select"; nextId: string }
  | { kind: "discard-tab"; nextStatus: IssueStatus }
  | null;

function toForm(issue: AdminIssue): EditForm {
  const opts = (issue.options || [])
    .slice()
    .sort((a, b) => a.display_order - b.display_order)
    .map((o) => o.label);
  return {
    title: issue.title || "",
    summary: issue.summary || "",
    why_it_matters: issue.why_it_matters || "",
    column_body: issue.column_body || "",
    column_author_name: issue.column_author_name || "",
    column_author_image_url: issue.column_author_image_url || "",
    columnist_id: issue.columnist_id || "",
    image_url: issue.image_url || "",
    key_points_text: (issue.key_points || []).join("\n"),
    category: issue.category || "",
    participation_suitable: Boolean(issue.participation_suitable),
    participation_question: issue.participation_question || "",
    participation_options_text: opts.join("\n"),
    show_sources: Boolean(issue.show_sources),
    push_title: issue.push_title || "",
    push_body: issue.push_body || "",
  };
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ko-KR");
  } catch {
    return iso;
  }
}

function lines(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function App() {
  const [key, setKey] = useState(
    () => localStorage.getItem(ADMIN_KEY_STORAGE) || "",
  );
  const [draftKey, setDraftKey] = useState(key);
  const [authed, setAuthed] = useState(Boolean(key));
  const [section, setSection] = useState<AdminSection>("issues");
  const [status, setStatus] = useState<IssueStatus>("draft");
  const [counts, setCounts] = useState<Counts | null>(null);
  const [items, setItems] = useState<AdminIssue[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminIssue | null>(null);
  const [form, setForm] = useState<EditForm | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<ModalState>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [columnists, setColumnists] = useState<AdminColumnist[]>([]);

  function applyDetail(issue: AdminIssue | null) {
    setDetail(issue);
    setForm(issue ? toForm(issue) : null);
    setDirty(false);
  }

  function patchForm(patch: Partial<EditForm>) {
    setForm((prev) => (prev ? { ...prev, ...patch } : prev));
    setDirty(true);
  }

  function closeModal() {
    if (busy) return;
    setModal(null);
    setRejectReason("");
  }

  async function refresh(
    nextStatus: IssueStatus = status,
    adminKey = key,
    selectId?: string | null,
  ) {
    setError(null);
    const [c, list] = await Promise.all([
      fetchCounts(adminKey),
      fetchIssues(adminKey, nextStatus),
    ]);
    setCounts(c);
    setItems(list.items);
    if (list.items.length === 0) {
      setSelectedId(null);
      applyDetail(null);
      return;
    }
    const want = selectId ?? selectedId;
    const keep = list.items.find((x) => x.id === want);
    const pick = keep?.id || list.items[0].id;
    setSelectedId(pick);
    applyDetail(await fetchIssue(adminKey, pick));
  }

  useEffect(() => {
    if (!authed || !key || section !== "issues") return;
    void refresh().catch((e) => {
      setError(e instanceof Error ? e.message : "불러오기 실패");
      setAuthed(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed, key, status, section]);

  useEffect(() => {
    if (!authed || !key) return;
    void fetchColumnists(key, "active")
      .then((list) => setColumnists(list.items))
      .catch(() => setColumnists([]));
  }, [authed, key, section]);

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    const next = draftKey.trim();
    if (!next) return;
    setBusy(true);
    setError(null);
    try {
      await fetchCounts(next);
      localStorage.setItem(ADMIN_KEY_STORAGE, next);
      setKey(next);
      setAuthed(true);
      setSection("issues");
    } catch (err) {
      setError(err instanceof Error ? err.message : "인증 실패");
      setAuthed(false);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    localStorage.removeItem(ADMIN_KEY_STORAGE);
    setKey("");
    setDraftKey("");
    setAuthed(false);
    setSection("issues");
    setItems([]);
    applyDetail(null);
  }

  async function onCreateColumnDraft(columnistId?: string) {
    if (section === "issues" && dirty) {
      setError(
        "저장하지 않은 이슈 변경이 있습니다. 저장하거나 버린 뒤 초안을 만드세요.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const row = await createIssue(key, {
        columnist_id: columnistId || null,
      });
      const needSwitch = section !== "issues" || status !== "draft";
      setSelectedId(row.id);
      applyDetail(row);
      setSection("issues");
      setStatus("draft");
      setNotice("칼럼 초안을 만들었습니다. 제목과 본문을 적어 주세요.");
      if (!needSwitch) {
        await refresh("draft", key, row.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "초안 만들기 실패");
    } finally {
      setBusy(false);
    }
  }

  function requestSection(next: AdminSection) {
    if (next === section) return;
    if (section === "issues" && dirty) {
      setError("저장하지 않은 이슈 변경이 있습니다. 저장하거나 탭을 바꾸기 전에 버리세요.");
      return;
    }
    setError(null);
    setNotice(null);
    setSection(next);
  }

  async function loadIssue(id: string) {
    setSelectedId(id);
    setError(null);
    try {
      applyDetail(await fetchIssue(key, id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "상세 실패");
    }
  }

  function requestSelect(id: string) {
    if (id === selectedId) return;
    if (dirty) {
      setModal({ kind: "discard-select", nextId: id });
      return;
    }
    void loadIssue(id);
  }

  function requestTab(next: IssueStatus) {
    if (next === status) return;
    if (dirty) {
      setModal({ kind: "discard-tab", nextStatus: next });
      return;
    }
    setStatus(next);
  }

  function buildUpdateBody(
    next: EditForm,
    extras: Partial<AdminIssueUpdate> = {},
  ): AdminIssueUpdate {
    const keyPoints = lines(next.key_points_text);
    const optionLines = lines(next.participation_options_text);
    return {
      title: next.title.trim(),
      summary: next.summary.trim(),
      why_it_matters: next.why_it_matters.trim(),
      column_body: next.column_body.trim(),
      columnist_id: next.columnist_id.trim() || null,
      clear_columnist: !next.columnist_id.trim(),
      column_author_name: null,
      column_author_image_url: null,
      clear_column_author_image: false,
      image_url: next.image_url.trim() || null,
      clear_image: !next.image_url.trim(),
      key_points: keyPoints,
      category: next.category.trim() || null,
      participation_suitable: next.participation_suitable,
      participation_question: next.participation_suitable
        ? next.participation_question.trim() || null
        : null,
      participation_options: next.participation_suitable ? optionLines : null,
      show_sources: next.show_sources,
      push_title: next.push_title.trim() || null,
      push_body: next.push_body.trim() || null,
      ...extras,
    };
  }

  async function onSave() {
    if (!detail || !form || busy) return;
    if (detail.status !== "draft" && detail.status !== "published") {
      setError("폐기된 이슈는 편집할 수 없습니다.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await updateIssue(key, detail.id, buildUpdateBody(form));
      applyDetail(saved);
      setItems((prev) =>
        prev.map((item) =>
          item.id === saved.id
            ? {
                ...item,
                title: saved.title,
                summary: saved.summary,
                category: saved.category,
                importance: saved.importance,
              }
            : item,
        ),
      );
      setNotice("저장했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  }

  async function openPublishModal() {
    if (!detail || busy) return;
    if (dirty) {
      setError("배포 전에 먼저 저장하세요.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const fresh = await fetchIssue(key, detail.id);
      applyDetail(fresh);
      setModal({ kind: "publish" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "배포 미리보기 불러오기 실패");
    } finally {
      setBusy(false);
    }
  }

  function openRejectModal() {
    if (!detail || busy) return;
    setRejectReason("");
    setModal({ kind: "reject" });
  }

  function openUnpublishModal() {
    if (!detail || busy) return;
    if (dirty) {
      setError("배포 취소 전에 먼저 저장하거나 변경을 버리세요.");
      return;
    }
    setModal({ kind: "unpublish" });
  }

  async function onUploadImage(file: File | null) {
    if (!detail || !file || busy) return;
    if (detail.status !== "draft" && detail.status !== "published") {
      setError("폐기된 이슈는 편집할 수 없습니다.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await uploadIssueImage(key, detail.id, file);
      applyDetail(saved);
      setNotice("대표 이미지 업로드 완료 — 앱 이슈 카드에 바로 반영됩니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "이미지 업로드 실패");
    } finally {
      setBusy(false);
    }
  }

  async function clearImage() {
    if (!detail || busy) return;
    if (detail.status !== "draft" && detail.status !== "published") {
      setError("폐기된 이슈는 편집할 수 없습니다.");
      return;
    }
    if (!form) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await updateIssue(
        key,
        detail.id,
        buildUpdateBody(form, { image_url: null, clear_image: true }),
      );
      applyDetail(saved);
      setNotice("대표 이미지를 제거했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "이미지 제거 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmPublish() {
    if (!detail || busy) return;
    const publishedId = detail.id;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await publishIssue(key, publishedId);
      setModal(null);
      setNotice("배포했습니다. 앱 홈에 노출됩니다.");
      setSelectedId(publishedId);
      setStatus("published");
      await refresh("published");
    } catch (err) {
      setError(err instanceof Error ? err.message : "배포 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmReject() {
    if (!detail || busy) return;
    const rejectedId = detail.id;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await rejectIssue(key, rejectedId, rejectReason.trim() || undefined);
      const wasPublished = detail.status === "published";
      setModal(null);
      setRejectReason("");
      setNotice(
        wasPublished ? "폐기했고 앱 홈에서 내렸습니다." : "폐기했습니다.",
      );
      setSelectedId(rejectedId);
      setStatus("rejected");
      await refresh("rejected");
    } catch (err) {
      setError(err instanceof Error ? err.message : "폐기 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmUnpublish() {
    if (!detail || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await unpublishIssue(key, detail.id);
      setModal(null);
      setNotice("배포 취소 → draft로 돌렸습니다. 앱에서 내려갑니다.");
      setStatus("draft");
      await refresh("draft");
    } catch (err) {
      setError(err instanceof Error ? err.message : "회수 실패");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDiscard() {
    if (!modal) return;
    if (modal.kind === "discard-select") {
      const id = modal.nextId;
      setModal(null);
      await loadIssue(id);
      return;
    }
    if (modal.kind === "discard-tab") {
      const next = modal.nextStatus;
      setModal(null);
      setDirty(false);
      setStatus(next);
    }
  }

  const canEdit = detail?.status === "draft" || detail?.status === "published";
  const issueTitle = detail?.title?.trim() || "이 이슈";

  if (!authed) {
    return (
      <div className="login-shell">
        <form className="login" onSubmit={(e) => void onLogin(e)}>
          <p className="brand-mark">TAKELEY</p>
          <h1>Admin</h1>
          <p className="login-dek">
            Take a look. Take a side. — Issue·Contributor 운영 포탈
          </p>
          <label htmlFor="admin-key">Admin API Key</label>
          <input
            id="admin-key"
            type="password"
            autoComplete="current-password"
            value={draftKey}
            onChange={(e) => setDraftKey(e.target.value)}
            placeholder="ADMIN_API_KEY"
          />
          <button type="submit" disabled={busy || !draftKey.trim()}>
            들어가기
          </button>
        </form>
        <ToastHost
          error={error}
          onDismissError={() => setError(null)}
        />
      </div>
    );
  }

  return (
    <div className="shell">
      <ToastHost
        notice={notice}
        error={error}
        onDismissNotice={() => setNotice(null)}
        onDismissError={() => setError(null)}
      />
      <header className="topbar">
        <div>
          <p className="brand-mark">TAKELEY · Admin</p>
        </div>
        <button type="button" className="logout" onClick={logout}>
          로그아웃
        </button>
      </header>

      <nav className="section-nav" aria-label="Admin sections">
        <button
          type="button"
          className={section === "issues" ? "is-active" : ""}
          onClick={() => requestSection("issues")}
        >
          Issues
        </button>
        <button
          type="button"
          className={section === "columnists" ? "is-active" : ""}
          onClick={() => requestSection("columnists")}
        >
          칼럼니스트
        </button>
        <button
          type="button"
          className={section === "applications" ? "is-active" : ""}
          onClick={() => requestSection("applications")}
        >
          Contributor
        </button>
        <button
          type="button"
          className={section === "takes" ? "is-active" : ""}
          onClick={() => requestSection("takes")}
        >
          깊이 있는 생각
        </button>
      </nav>

      {section === "columnists" ? (
        <ColumnistsPanel
          adminKey={key}
          onAuthFailure={() => setAuthed(false)}
          onStartColumnDraft={(id) => void onCreateColumnDraft(id)}
        />
      ) : null}

      {section === "applications" ? (
        <ContributorApplicationsPanel
          adminKey={key}
          onAuthFailure={() => setAuthed(false)}
        />
      ) : null}

      {section === "takes" ? (
        <DeepThoughtsPanel
          adminKey={key}
          onAuthFailure={() => setAuthed(false)}
        />
      ) : null}

      {section === "issues" ? (
        <>
          <div className="tabs">
            {(
              [
                ["draft", "초안"],
                ["published", "배포"],
                ["rejected", "폐기"],
              ] as const
            ).map(([s, label]) => (
              <button
                key={s}
                type="button"
                className={status === s ? "is-active" : ""}
                onClick={() => requestTab(s)}
              >
                {label}
                {counts ? ` · ${counts[s]}` : ""}
              </button>
            ))}
            <button
              type="button"
              className="tabs__ghost"
              disabled={busy}
              onClick={() => void onCreateColumnDraft()}
            >
              칼럼 초안
            </button>
          </div>

          <div className="layout">
            <aside className="panel">
              <ul className="list">
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={selectedId === item.id ? "is-selected" : ""}
                      onClick={() => requestSelect(item.id)}
                    >
                      <span className="cat">{item.category || "ISSUE"}</span>
                      <p className="title">{item.title}</p>
                      <p className="meta">
                        {formatWhen(item.first_seen_at)} · 출처{" "}
                        {item.source_count} · imp {item.importance.toFixed(2)}
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
              {!detail || !form ? (
                <div className="empty">왼쪽에서 이슈를 선택하세요.</div>
              ) : (
            <>
              <p className="meta">
                status {detail.status} · {formatWhen(detail.first_seen_at)}
                {dirty ? " · 수정됨" : ""}
              </p>

              {detail.status === "published" ? (
                <p className="meta">
                  배포된 글입니다. 저장은 앱에 바로 반영되고 푸시는 보내지 않습니다.
                  홈에서 내리려면 배포 취소를 쓰세요.
                </p>
              ) : null}
              {!canEdit ? (
                <p className="meta">폐기된 이슈는 편집할 수 없습니다.</p>
              ) : null}

              <div className={`editor${canEdit ? "" : " editor--readonly"}`}>
                <div className="editor-section">
                  <p className="editor-section__title">카드</p>
                  <p className="editor-section__dek">
                    홈·상세에 바로 보이는 핵심 문구
                  </p>
                <label>
                  카테고리
                  <select
                    value={form.category}
                    disabled={!canEdit}
                    onChange={(e) => patchForm({ category: e.target.value })}
                  >
                    <option value="">(없음)</option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  제목
                  <span className="field-hint">앱 이슈 카드에 표시</span>
                  <textarea
                    className="title-input"
                    rows={2}
                    value={form.title}
                    disabled={!canEdit}
                    onChange={(e) => patchForm({ title: e.target.value })}
                  />
                </label>

                <div className="image-field">
                  <span className="image-field__label">
                    {canEdit
                      ? "대표 이미지 · 업로드/제거는 즉시 저장"
                      : "대표 이미지"}
                  </span>
                  {resolveMediaUrl(form.image_url) ? (
                    <img
                      className="image-field__preview"
                      src={resolveMediaUrl(form.image_url) || ""}
                      alt="대표 이미지 미리보기"
                    />
                  ) : (
                    <div className="image-field__empty">대표 이미지 없음</div>
                  )}
                  {canEdit ? (
                    <div className="image-field__row">
                      <label className="image-field__file">
                        파일 업로드
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,image/gif"
                          disabled={busy}
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null;
                            e.target.value = "";
                            void onUploadImage(file);
                          }}
                        />
                      </label>
                      {form.image_url ? (
                        <button
                          type="button"
                          className="image-field__clear"
                          disabled={busy}
                          onClick={() => void clearImage()}
                        >
                          이미지 제거
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  <label className="image-field__url">
                    대표 이미지 URL
                    {canEdit ? " (변경 후 저장 필요)" : ""}
                    <input
                      type="text"
                      value={form.image_url}
                      placeholder="https://… 또는 업로드"
                      disabled={!canEdit}
                      onChange={(e) =>
                        patchForm({ image_url: e.target.value })
                      }
                    />
                  </label>
                  {canEdit ? (
                    <p className="image-field__hint">
                      앱 이슈 카드·상세 상단에 표시됩니다. 카드 본문은
                      제목·요약만 보입니다.
                    </p>
                  ) : null}
                </div>

                <label>
                  요약
                  <span className="field-hint">앱 이슈 카드에 표시</span>
                  <textarea
                    rows={3}
                    value={form.summary}
                    disabled={!canEdit}
                    onChange={(e) => patchForm({ summary: e.target.value })}
                  />
                </label>

                <label>
                  왜 중요한가
                  <textarea
                    rows={3}
                    value={form.why_it_matters}
                    disabled={!canEdit}
                    onChange={(e) =>
                      patchForm({ why_it_matters: e.target.value })
                    }
                  />
                </label>

                <label>
                  핵심 (한 줄에 하나)
                  <textarea
                    rows={4}
                    value={form.key_points_text}
                    disabled={!canEdit}
                    onChange={(e) =>
                      patchForm({ key_points_text: e.target.value })
                    }
                    />
                  </label>
                </div>

                <div className="editor-section">
                  <p className="editor-section__title">칼럼</p>
                  <p className="editor-section__dek">
                    상세에서 길게 읽는 본문
                  </p>

                <div className="column-field">
                  <span className="column-field__label">테이클리 칼럼니스트</span>
                  <span className="field-hint">
                    선정 필진에서 고릅니다. 이름·사진은 프로필에서 관리합니다.
                  </span>
                  <div className="author-byline-admin">
                    {(() => {
                      const picked =
                        columnists.find((c) => c.id === form.columnist_id) ||
                        null;
                      const photo = resolveMediaUrl(
                        picked?.image_url || form.column_author_image_url,
                      );
                      const label = (
                        picked?.display_name ||
                        form.column_author_name ||
                        "?"
                      ).trim();
                      return photo ? (
                        <img
                          className="author-byline-admin__avatar"
                          src={photo}
                          alt=""
                        />
                      ) : (
                        <div className="author-byline-admin__avatar author-byline-admin__avatar--empty">
                          {(label.slice(0, 1) || "?").toUpperCase()}
                        </div>
                      );
                    })()}
                    <div className="author-byline-admin__fields">
                      <select
                        value={form.columnist_id}
                        disabled={!canEdit}
                        onChange={(e) =>
                          patchForm({ columnist_id: e.target.value })
                        }
                      >
                        <option value="">없음</option>
                        {columnists.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.display_name}
                            {c.headline ? ` · ${c.headline}` : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div className="column-field">
                  <span className="column-field__label">칼럼 본문</span>
                  <span className="field-hint">앱 · 컬럼 자세히 보기</span>
                  <ColumnEditor
                    adminKey={key}
                    issueId={detail.id}
                    value={form.column_body}
                    busy={busy}
                    readOnly={!canEdit}
                    onChange={(next) => patchForm({ column_body: next })}
                    onError={(msg) => setError(msg)}
                  />
                </div>
                </div>

                <div className="editor-section">
                  <p className="editor-section__title">참여 · 알림</p>
                  <p className="editor-section__dek">
                    투표와 푸시 문구 (비우면 자동)
                  </p>

                <label className="check">
                  <input
                    type="checkbox"
                    checked={form.participation_suitable}
                    disabled={!canEdit}
                    onChange={(e) =>
                      patchForm({
                        participation_suitable: e.target.checked,
                      })
                    }
                  />
                  <span>
                    <strong>참여 가능</strong>
                    <em>앱에서 생각을 남길 수 있어요</em>
                  </span>
                </label>

                {form.participation_suitable ? (
                  <>
                    <label>
                      참여 질문
                      <textarea
                        rows={2}
                        value={form.participation_question}
                        disabled={!canEdit}
                        onChange={(e) =>
                          patchForm({
                            participation_question: e.target.value,
                          })
                        }
                      />
                    </label>
                    <label>
                      선택지 (한 줄에 하나, 최소 2개)
                      <textarea
                        rows={3}
                        value={form.participation_options_text}
                        disabled={!canEdit}
                        onChange={(e) =>
                          patchForm({
                            participation_options_text: e.target.value,
                          })
                        }
                      />
                    </label>
                  </>
                ) : null}

                <label>
                  알림 제목 (선택 · 비우면 자동)
                  <input
                    type="text"
                    maxLength={80}
                    value={form.push_title}
                    disabled={!canEdit}
                    placeholder="비우면 이슈 제목 기반 자동 문구"
                    onChange={(e) => patchForm({ push_title: e.target.value })}
                  />
                </label>
                <label>
                  알림 본문 (선택 · 비우면 자동)
                  <textarea
                    rows={2}
                    maxLength={160}
                    value={form.push_body}
                    disabled={!canEdit}
                    placeholder="비우면 참여 질문 또는 확인 CTA 자동"
                    onChange={(e) => patchForm({ push_body: e.target.value })}
                  />
                </label>
                </div>

                <div className="editor-section">
                  <p className="editor-section__title">출처</p>
                  <p className="editor-section__dek">
                    앱 노출 여부와 원문 링크
                  </p>

                <label className="check">
                  <input
                    type="checkbox"
                    checked={form.show_sources}
                    disabled={!canEdit}
                    onChange={(e) =>
                      patchForm({ show_sources: e.target.checked })
                    }
                  />
                  <span>
                    <strong>출처 노출</strong>
                    <em>끄면 앱에서 출처 수·크레딧이 숨겨집니다</em>
                  </span>
                </label>

                {(detail.sources || []).length > 0 ? (
                  <div className="section">
                    <h3>
                      출처 (읽기 전용)
                      {!form.show_sources ? " · 앱 비노출" : ""}
                    </h3>
                    <ul className="source-url-list">
                      {(detail.sources || []).map((s) => {
                        const label = s.author || s.provider || "원문";
                        return (
                          <li key={s.id}>
                            {s.url ? (
                              <a
                                href={s.url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {label}
                              </a>
                            ) : (
                              <span>{label}</span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ) : null}
                </div>
              </div>

              <div className="actions">
                {canEdit ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={busy || !dirty}
                    onClick={() => void onSave()}
                  >
                    저장
                  </button>
                ) : null}
                {detail.status === "draft" ? (
                  <>
                    <button
                      type="button"
                      className="primary"
                      disabled={busy || dirty}
                      onClick={() => void openPublishModal()}
                    >
                      배포
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={openRejectModal}
                    >
                      폐기
                    </button>
                  </>
                ) : null}
                {detail.status === "published" ? (
                  <>
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy}
                      onClick={openUnpublishModal}
                    >
                      배포 취소
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={openRejectModal}
                    >
                      폐기
                    </button>
                  </>
                ) : null}
              </div>
            </>
          )}
        </section>
      </div>

      <ConfirmModal
        open={modal?.kind === "publish"}
        title="정말 배포할까요?"
        body={`「${issueTitle}」를 지금 배포하면 앱 홈에 공개되고, 알림을 켠 사용자에게 아래 푸시가 발송됩니다. 내용을 한 번 더 확인해 주세요.`}
        confirmLabel="배포하기"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmPublish()}
      >
        <div className="push-preview" aria-label="발송될 알림 미리보기">
          <p className="push-preview__label">
            알림 미리보기
            {detail?.push_kind ? (
              <span className="push-preview__kind">
                {detail.push_kind === "participation"
                  ? "참여"
                  : detail.push_kind === "trend"
                    ? "급상승/트렌딩"
                    : "일반"}
                {detail.push_title || detail.push_body ? " · 직접 입력" : " · 자동"}
              </span>
            ) : null}
          </p>
          <div className="push-preview__card">
            <p className="push-preview__title">
              {detail?.push_preview_title || issueTitle}
            </p>
            <p className="push-preview__body">
              {detail?.push_preview_body || "새롭게 나온 내용을 확인해보세요."}
            </p>
          </div>
        </div>
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "reject"}
        title="폐기할까요?"
        body={
          detail?.status === "published"
            ? `「${issueTitle}」를 폐기하고 앱에서 내립니다.`
            : `「${issueTitle}」를 폐기합니다. 다시 배포하려면 새 초안이 필요합니다.`
        }
        confirmLabel="폐기"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmReject()}
      >
        <label className="modal-field">
          폐기 사유 (선택)
          <textarea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="예: 사실 확인 부족, 중복 이슈…"
            disabled={busy}
          />
        </label>
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "unpublish"}
        title="배포를 취소할까요?"
        body={`「${issueTitle}」를 draft로 되돌리고 앱에서 내립니다.`}
        confirmLabel="배포 취소"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmUnpublish()}
      />

      <ConfirmModal
        open={
          modal?.kind === "discard-select" || modal?.kind === "discard-tab"
        }
        title="저장하지 않은 변경"
        body="저장하지 않은 수정이 있습니다. 버리고 이동할까요?"
        confirmLabel="버리고 이동"
        tone="danger"
        busy={busy}
        onCancel={closeModal}
        onConfirm={() => void confirmDiscard()}
      />
        </>
      ) : null}
    </div>
  );
}
