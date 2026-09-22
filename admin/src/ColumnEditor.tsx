import { useLayoutEffect, useRef, useState } from "react";
import { resolveMediaUrl, uploadColumnMedia } from "./api";
import { ColumnMarkdownView } from "./columnMarkdown";

type Props = {
  adminKey: string;
  issueId: string;
  value: string;
  busy?: boolean;
  readOnly?: boolean;
  onChange: (next: string) => void;
  onError?: (message: string) => void;
};

function wrapSelection(
  value: string,
  start: number,
  end: number,
  before: string,
  after: string,
): { next: string; selStart: number; selEnd: number } {
  const selected = value.slice(start, end) || "텍스트";
  const next =
    value.slice(0, start) + before + selected + after + value.slice(end);
  const selStart = start + before.length;
  const selEnd = selStart + selected.length;
  return { next, selStart, selEnd };
}

export function ColumnEditor({
  adminKey,
  issueId,
  value,
  busy = false,
  readOnly = false,
  onChange,
  onError,
}: Props) {
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const pendingSel = useRef<{ start: number; end: number } | null>(null);
  const savedRange = useRef<{ start: number; end: number } | null>(null);
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [uploading, setUploading] = useState(false);

  useLayoutEffect(() => {
    if (readOnly) return;
    const el = areaRef.current;
    const sel = pendingSel.current;
    if (!el || !sel) return;
    el.focus();
    el.setSelectionRange(sel.start, sel.end);
    pendingSel.current = null;
  }, [value, readOnly]);

  if (readOnly) {
    return (
      <div className="column-editor column-editor--readonly">
        <div className="column-editor__preview">
          <ColumnMarkdownView
            source={value}
            resolveUrl={(u) => resolveMediaUrl(u) || u}
            emptyText="칼럼 본문 없음"
          />
        </div>
      </div>
    );
  }

  function commit(next: string, start: number, end: number = start) {
    pendingSel.current = { start, end };
    onChange(next);
  }

  function readRange(): { start: number; end: number } {
    const el = areaRef.current;
    if (!el) return { start: value.length, end: value.length };
    return { start: el.selectionStart, end: el.selectionEnd };
  }

  /** Prevent toolbar buttons from stealing focus (which resets caret to 0). */
  function keepFocus(e: React.MouseEvent) {
    e.preventDefault();
  }

  function applyWrap(before: string, after: string) {
    const { start, end } = readRange();
    const { next, selStart, selEnd } = wrapSelection(
      value,
      start,
      end,
      before,
      after,
    );
    commit(next, selStart, selEnd);
  }

  function applyHeading() {
    const { start } = readRange();
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    const lineEnd = value.indexOf("\n", start);
    const end = lineEnd === -1 ? value.length : lineEnd;
    const line = value.slice(lineStart, end);
    const headed = line.startsWith("## ")
      ? line
      : `## ${line.replace(/^#+\s*/, "") || "소제목"}`;
    // Ensure the heading stands alone (blank lines) for readable source.
    const before = value.slice(0, lineStart);
    const after = value.slice(end);
    const prefix = before && !before.endsWith("\n\n")
      ? before.replace(/\n?$/, "\n\n")
      : before;
    const suffix = after && !after.startsWith("\n\n")
      ? after.replace(/^\n?/, "\n\n")
      : after;
    const next = prefix + headed + suffix;
    const pos = prefix.length + headed.length;
    commit(next, pos);
  }

  function applyLink() {
    const { start, end } = readRange();
    const selected = value.slice(start, end) || "링크 텍스트";
    const url = window.prompt("링크 URL", "https://");
    if (!url) return;
    const snippet = `[${selected}](${url.trim()})`;
    const next = value.slice(0, start) + snippet + value.slice(end);
    const pos = start + snippet.length;
    commit(next, pos);
  }

  async function onPickImage(file: File | null) {
    if (!file || uploading || busy) return;
    const range = savedRange.current ?? readRange();
    savedRange.current = null;
    const { start, end } = range;
    setUploading(true);
    try {
      const { url } = await uploadColumnMedia(adminKey, issueId, file);
      const current = areaRef.current?.value ?? value;
      const snippet = `\n\n![이미지](${url})\n\n`;
      const next = current.slice(0, start) + snippet + current.slice(end);
      commit(next, start + snippet.length);
      setMode("edit");
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "이미지 업로드 실패");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="column-editor">
      <div className="column-editor__bar">
        <div className="column-editor__tools">
          <button
            type="button"
            disabled={busy || uploading || mode === "preview"}
            onMouseDown={keepFocus}
            onClick={() => applyWrap("**", "**")}
            title="굵게"
          >
            B
          </button>
          <button
            type="button"
            disabled={busy || uploading || mode === "preview"}
            onMouseDown={keepFocus}
            onClick={() => applyWrap("*", "*")}
            title="기울임"
          >
            I
          </button>
          <button
            type="button"
            disabled={busy || uploading || mode === "preview"}
            onMouseDown={keepFocus}
            onClick={applyHeading}
            title="소제목"
          >
            H
          </button>
          <button
            type="button"
            disabled={busy || uploading || mode === "preview"}
            onMouseDown={keepFocus}
            onClick={applyLink}
            title="링크"
          >
            링크
          </button>
          <button
            type="button"
            disabled={busy || uploading || mode === "preview"}
            onMouseDown={keepFocus}
            onClick={() => {
              savedRange.current = readRange();
              fileRef.current?.click();
            }}
            title="이미지 삽입"
          >
            {uploading ? "업로드…" : "이미지"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0] || null;
              e.target.value = "";
              void onPickImage(f);
            }}
          />
        </div>
        <div className="column-editor__modes">
          <button
            type="button"
            className={mode === "edit" ? "is-active" : ""}
            disabled={busy}
            onMouseDown={keepFocus}
            onClick={() => setMode("edit")}
          >
            편집
          </button>
          <button
            type="button"
            className={mode === "preview" ? "is-active" : ""}
            disabled={busy}
            onMouseDown={keepFocus}
            onClick={() => setMode("preview")}
          >
            미리보기
          </button>
        </div>
      </div>

      {mode === "edit" ? (
        <textarea
          ref={areaRef}
          className="column-input"
          rows={24}
          value={value}
          disabled={busy || uploading}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            "## 소제목\n\n본문을 적어 주세요. **굵게**, *기울임*, ***둘 다***, 이미지도 넣을 수 있어요."
          }
        />
      ) : (
        <div className="column-editor__preview">
          <ColumnMarkdownView
            source={value}
            resolveUrl={(u) => resolveMediaUrl(u) || u}
            emptyText="미리볼 본문이 없어요."
          />
        </div>
      )}
      <p className="column-editor__hint">
        Markdown · 굵게 **텍스트** · 기울임 *텍스트* · 둘 다 ***텍스트*** · 소제목
        ## · 이미지는 본문 중간에 삽입됩니다. 저장 후 앱 칼럼에 반영돼요.
      </p>
    </div>
  );
}
