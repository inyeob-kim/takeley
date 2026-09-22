/** Shared Admin label helpers for Contributor moderation. */

export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ko-KR");
  } catch {
    return iso;
  }
}

export function contributorStatusLabel(status: string): string {
  switch (status) {
    case "NONE":
      return "미신청";
    case "PENDING":
      return "심사 중";
    case "APPROVED":
      return "승인";
    case "REJECTED":
      return "반려";
    case "SUSPENDED":
      return "정지";
    default:
      return status;
  }
}

export function applicationStatusLabel(status: string): string {
  switch (status) {
    case "PENDING":
      return "심사 중";
    case "APPROVED":
      return "승인";
    case "REJECTED":
      return "반려";
    default:
      return status;
  }
}

export function takeStatusLabel(status: string): string {
  switch (status) {
    case "draft":
      return "작성 중";
    case "pending_review":
      return "검토 중";
    case "published":
      return "게시됨";
    case "rejected":
      return "반려";
    default:
      return status;
  }
}

/** Documented backend unpublish transition. */
export const TAKE_UNPUBLISH_RESULT: "rejected" = "rejected";
