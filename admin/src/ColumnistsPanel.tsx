import { useEffect, useState } from "react";
import {
  createColumnist,
  fetchColumnists,
  resolveMediaUrl,
  updateColumnist,
  uploadColumnistImage,
  type AdminColumnist,
  type ColumnistStatus,
} from "./api";
import { formatWhen } from "./contributorLabels";
import { ToastHost } from "./ToastHost";

type Props = {
  adminKey: string;
  onAuthFailure?: () => void;
  onStartColumnDraft?: (columnistId: string) => void;
};

type Form = {
  display_name: string;
  headline: string;
  bio: string;
  specialties: string;
  contact_email: string;
  show_email: boolean;
  profile_public: boolean;
  status: ColumnistStatus;
};

function specialtiesToText(items?: string[] | null): string {
  return (items || []).join("\n");
}

function textToSpecialties(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 12);
}

function emptyForm(): Form {
  return {
    display_name: "",
    headline: "",
    bio: "",
    specialties: "",
    contact_email: "",
    show_email: false,
    profile_public: true,
    status: "active",
  };
}

function toForm(row: AdminColumnist): Form {
  return {
    display_name: row.display_name || "",
    headline: row.headline || "",
    bio: row.bio || "",
    specialties: specialtiesToText(row.specialties),
    contact_email: row.contact_email || "",
    show_email: Boolean(row.show_email),
    profile_public: row.profile_public !== false,
    status: row.status,
  };
}

function statusLabel(status: ColumnistStatus): string {
  return status === "archived" ? "보관" : "선정";
}

export function ColumnistsPanel({
  adminKey,
  onAuthFailure,
  onStartColumnDraft,
}: Props) {
  const [filter, setFilter] = useState<ColumnistStatus | "all">("active");
  const [items, setItems] = useState<AdminColumnist[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<Form>(emptyForm());
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selected = creating
    ? null
    : items.find((x) => x.id === selectedId) || null;
  const showEditor = creating || Boolean(selected);

  function setLocalPhoto(file: File | null) {
    setPendingPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return file ? URL.createObjectURL(file) : null;
    });
    setPendingFile(file);
  }

  async function refresh(
    nextFilter: ColumnistStatus | "all" = filter,
    selectId?: string | null,
  ) {
    setError(null);
    try {
      const status = nextFilter === "all" ? undefined : nextFilter;
      const list = await fetchColumnists(adminKey, status);
      setItems(list.items);
      if (creating && selectId == null) return;
      if (list.items.length === 0) {
        setSelectedId(null);
        setForm(emptyForm());
        return;
      }
      const want = selectId ?? selectedId;
      const keep = list.items.find((x) => x.id === want);
      const pick = keep || list.items[0];
      setSelectedId(pick.id);
      setForm(toForm(pick));
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
  }, [adminKey, filter]);

  useEffect(() => {
    return () => {
      if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startCreate() {
    setCreating(true);
    setSelectedId(null);
    setForm(emptyForm());
    setLocalPhoto(null);
  }

  function selectRow(row: AdminColumnist) {
    setCreating(false);
    setSelectedId(row.id);
    setForm(toForm(row));
    setLocalPhoto(null);
  }

  async function onSave() {
    const name = form.display_name.trim();
    if (!name || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (creating) {
        let row = await createColumnist(adminKey, {
          display_name: name,
          headline: form.headline.trim(),
          bio: form.bio.trim(),
          specialties: textToSpecialties(form.specialties),
          contact_email: form.contact_email.trim() || null,
          show_email: Boolean(form.contact_email.trim()) && form.show_email,
          profile_public: form.profile_public,
          status: form.status,
        });
        if (pendingFile) {
          row = await uploadColumnistImage(adminKey, row.id, pendingFile);
        }
        setLocalPhoto(null);
        setCreating(false);
        setSelectedId(row.id);
        setNotice("칼럼니스트를 등록했습니다.");
        await refresh(filter, row.id);
      } else if (selected) {
        const row = await updateColumnist(adminKey, selected.id, {
          display_name: name,
          headline: form.headline.trim(),
          bio: form.bio.trim(),
          specialties: textToSpecialties(form.specialties),
          contact_email: form.contact_email.trim() || "",
          show_email: Boolean(form.contact_email.trim()) && form.show_email,
          profile_public: form.profile_public,
          status: form.status,
        });
        setItems((prev) => prev.map((x) => (x.id === row.id ? row : x)));
        setForm(toForm(row));
        setNotice("저장했습니다.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File) {
    if (busy) return;
    if (creating) {
      setLocalPhoto(file);
      return;
    }
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const row = await uploadColumnistImage(adminKey, selected.id, file);
      setItems((prev) => prev.map((x) => (x.id === row.id ? row : x)));
      setNotice("사진을 올렸습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "사진 업로드 실패");
    } finally {
      setBusy(false);
    }
  }

  async function onClearImage() {
    if (!selected || creating || busy) return;
    setBusy(true);
    setError(null);
    try {
      const row = await updateColumnist(adminKey, selected.id, {
        clear_image: true,
      });
      setItems((prev) => prev.map((x) => (x.id === row.id ? row : x)));
      setNotice("사진을 지웠습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "사진 제거 실패");
    } finally {
      setBusy(false);
    }
  }

  const photo =
    pendingPreview || (selected ? resolveMediaUrl(selected.image_url) : null);
  const heading = creating
    ? "새 칼럼니스트"
    : form.display_name.trim() || selected?.display_name || "칼럼니스트";

  return (
    <>
      <ToastHost
        notice={notice}
        error={error}
        onDismissNotice={() => setNotice(null)}
        onDismissError={() => setError(null)}
      />

      <div className="tabs">
        {(
          [
            ["active", "선정"],
            ["archived", "보관"],
            ["all", "전체"],
          ] as const
        ).map(([s, label]) => (
          <button
            key={s}
            type="button"
            className={filter === s ? "is-active" : ""}
            onClick={() => {
              setCreating(false);
              setFilter(s);
            }}
          >
            {label}
          </button>
        ))}
        <button type="button" className="tabs__ghost" onClick={startCreate}>
          새로 등록
        </button>
      </div>

      <div className="layout">
        <aside className="panel">
          <ul className="list">
            {creating ? (
              <li>
                <button type="button" className="is-selected">
                  <span className="cat">NEW</span>
                  <p className="title">새 칼럼니스트</p>
                  <p className="meta">아직 저장되지 않았어요</p>
                </button>
              </li>
            ) : null}
            {items.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className={
                    !creating && selectedId === row.id ? "is-selected" : ""
                  }
                  onClick={() => selectRow(row)}
                >
                  <span className="cat">{statusLabel(row.status)}</span>
                  <p className="title">{row.display_name}</p>
                  <p className="meta">
                    {row.profile_public === false ? "프로필 비공개 · " : ""}
                    {row.headline || "테이클리 칼럼니스트"}
                    {row.created_at ? ` · ${formatWhen(row.created_at)}` : ""}
                  </p>
                </button>
              </li>
            ))}
            {items.length === 0 && !creating ? (
              <li>
                <button type="button" disabled>
                  <p className="title">항목이 없어요</p>
                </button>
              </li>
            ) : null}
          </ul>
        </aside>

        <section className="panel detail">
          {!showEditor ? (
            <div className="empty">왼쪽에서 고르거나 새로 등록하세요.</div>
          ) : (
            <>
              <p className="meta">
                {creating
                  ? "status draft"
                  : `status ${selected?.status || form.status}`}
                {selected?.created_at
                  ? ` · ${formatWhen(selected.created_at)}`
                  : ""}
              </p>
              <span className="cat">COLUMNIST</span>
              <h2>{heading}</h2>
              <p className="summary">
                테이클리가 선정한 편집 필진입니다. 기여자와는 다릅니다.
              </p>

              <div className="editor">
                <div className="editor-section">
                  <p className="editor-section__title">프로필</p>
                  <p className="editor-section__dek">
                    앱 칼럼 바이라인과 프로필에 표시됩니다
                  </p>

                  <div className="image-field">
                    <span className="image-field__label">
                      {creating
                        ? "대표 사진 · 등록할 때 함께 저장"
                        : "대표 사진 · 업로드/제거는 즉시 저장"}
                    </span>
                    {photo ? (
                      <img
                        className="image-field__preview image-field__preview--avatar"
                        src={photo}
                        alt=""
                      />
                    ) : (
                      <div className="image-field__empty image-field__empty--avatar">
                        {(form.display_name.trim().slice(0, 1) || "?").toUpperCase()}
                      </div>
                    )}
                    <div className="image-field__row">
                      <label className="image-field__file">
                        업로드
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,image/gif"
                          disabled={busy}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            e.target.value = "";
                            if (file) void onUpload(file);
                          }}
                        />
                      </label>
                      {creating && pendingFile ? (
                        <button
                          type="button"
                          className="image-field__clear"
                          disabled={busy}
                          onClick={() => setLocalPhoto(null)}
                        >
                          제거
                        </button>
                      ) : null}
                      {!creating && selected?.image_url ? (
                        <button
                          type="button"
                          className="image-field__clear"
                          disabled={busy}
                          onClick={() => void onClearImage()}
                        >
                          제거
                        </button>
                      ) : null}
                    </div>
                  </div>

                  <label>
                    이름
                    <input
                      type="text"
                      maxLength={128}
                      value={form.display_name}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, display_name: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    한 줄 소개
                    <span className="field-hint">프로필 이름 아래</span>
                    <input
                      type="text"
                      maxLength={160}
                      value={form.headline}
                      placeholder="예: 전 특파원 · 국제정치"
                      onChange={(e) =>
                        setForm((f) => ({ ...f, headline: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    이메일
                    <span className="field-hint">문의용 · 선택</span>
                    <input
                      type="text"
                      inputMode="email"
                      autoComplete="email"
                      maxLength={254}
                      value={form.contact_email}
                      placeholder="writer@example.com"
                      onChange={(e) =>
                        setForm((f) => ({ ...f, contact_email: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    이메일 공개
                    <select
                      value={form.show_email ? "public" : "hidden"}
                      disabled={!form.contact_email.trim()}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          show_email: e.target.value === "public",
                        }))
                      }
                    >
                      <option value="hidden">프로필에 안 보임</option>
                      <option value="public">프로필 바이라인에 표시</option>
                    </select>
                  </label>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={!form.profile_public}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          profile_public: !e.target.checked,
                        }))
                      }
                    />
                    <span>
                      <strong>프로필 비공개</strong>
                      <em>이슈 바이라인은 남고, 탭해서 프로필로 들어가지 않습니다</em>
                    </span>
                  </label>
                </div>

                <div className="editor-section">
                  <p className="editor-section__title">소개</p>
                  <p className="editor-section__dek">
                    전문분야는 짧게, 소개는 한두 문장 — 같은 말을 반복하지 마세요
                  </p>
                  <label>
                    전문분야
                    <span className="field-hint">한 줄에 하나 · 최대 12개</span>
                    <textarea
                      rows={5}
                      value={form.specialties}
                      placeholder={"재산세제(양도, 상속, 증여)\n재개발 · 재건축 세제"}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, specialties: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    이력 · 소개
                    <span className="field-hint">한두 문장 · 전문분야와 겹치지 않게</span>
                    <textarea
                      rows={4}
                      value={form.bio}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, bio: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    상태
                    <select
                      value={form.status}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          status: e.target.value as ColumnistStatus,
                        }))
                      }
                    >
                      <option value="active">선정 — 이슈에 선택 가능</option>
                      <option value="archived">보관 — 선택 목록에서 숨김</option>
                    </select>
                  </label>
                </div>
              </div>

              <div className="actions">
                <button
                  type="button"
                  className="primary"
                  disabled={busy || !form.display_name.trim()}
                  onClick={() => void onSave()}
                >
                  {creating ? "등록" : "저장"}
                </button>
                {!creating && selected && onStartColumnDraft ? (
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy || selected.status !== "active"}
                    onClick={() => onStartColumnDraft(selected.id)}
                  >
                    칼럼 초안
                  </button>
                ) : null}
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
