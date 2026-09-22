import { useEffect, useRef } from "react";

type Props = {
  notice?: string | null;
  error?: string | null;
  onDismissNotice?: () => void;
  onDismissError?: () => void;
  noticeMs?: number;
  errorMs?: number;
};

export function ToastHost({
  notice,
  error,
  onDismissNotice,
  onDismissError,
  noticeMs = 4200,
  errorMs = 6500,
}: Props) {
  const dismissNoticeRef = useRef(onDismissNotice);
  const dismissErrorRef = useRef(onDismissError);
  dismissNoticeRef.current = onDismissNotice;
  dismissErrorRef.current = onDismissError;

  useEffect(() => {
    if (!notice) return;
    const t = window.setTimeout(() => dismissNoticeRef.current?.(), noticeMs);
    return () => window.clearTimeout(t);
  }, [notice, noticeMs]);

  useEffect(() => {
    if (!error) return;
    const t = window.setTimeout(() => dismissErrorRef.current?.(), errorMs);
    return () => window.clearTimeout(t);
  }, [error, errorMs]);

  if (!notice && !error) return null;

  return (
    <div className="toast-host" aria-live="polite" aria-relevant="additions">
      {error ? (
        <div className="toast toast--error" role="alert">
          <p className="toast__text">{error}</p>
          {onDismissError ? (
            <button
              type="button"
              className="toast__close"
              aria-label="닫기"
              onClick={onDismissError}
            >
              ×
            </button>
          ) : null}
        </div>
      ) : null}
      {notice ? (
        <div className="toast toast--info" role="status">
          <p className="toast__text">{notice}</p>
          {onDismissNotice ? (
            <button
              type="button"
              className="toast__close"
              aria-label="닫기"
              onClick={onDismissNotice}
            >
              ×
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
