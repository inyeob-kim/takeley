import { API_BASE_URL } from "./config";

export type IssueStatus = "draft" | "published" | "rejected";

export type ParticipationOption = {
  id: string;
  label: string;
  display_order: number;
  count?: number;
};

export type AdminIssue = {
  id: string;
  title: string;
  summary: string;
  why_it_matters: string;
  column_body?: string;
  column_author_name?: string | null;
  column_author_image_url?: string | null;
  columnist_id?: string | null;
  image_url?: string | null;
  key_points: string[];
  category: string | null;
  status: string;
  source_count: number;
  importance: number;
  first_seen_at: string | null;
  published_at: string | null;
  participation_suitable: boolean;
  participation_question: string | null;
  show_sources?: boolean;
  push_title?: string | null;
  push_body?: string | null;
  push_preview_title?: string | null;
  push_preview_body?: string | null;
  push_kind?: string | null;
  options?: ParticipationOption[];
  sources?: {
    id: string;
    url: string | null;
    provider: string | null;
    author?: string | null;
  }[];
};

export type AdminIssueUpdate = {
  title: string;
  summary: string;
  why_it_matters: string;
  column_body: string;
  column_author_name: string | null;
  column_author_image_url: string | null;
  clear_column_author_image?: boolean;
  columnist_id?: string | null;
  clear_columnist?: boolean;
  image_url: string | null;
  clear_image?: boolean;
  key_points: string[];
  category: string | null;
  participation_suitable: boolean;
  participation_question: string | null;
  participation_options: string[] | null;
  show_sources: boolean;
  push_title: string | null;
  push_body: string | null;
};

export type Counts = {
  draft: number;
  published: number;
  rejected: number;
};

export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const text = url.trim();
  if (!text) return null;
  if (/^https?:\/\//i.test(text)) return text;
  return `${API_BASE_URL}${text.startsWith("/") ? "" : "/"}${text}`;
}

async function adminFetch<T>(
  path: string,
  key: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Admin-Key": key,
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function fetchCounts(key: string): Promise<Counts> {
  return adminFetch<Counts>("/api/v1/admin/issues/counts", key);
}

export function fetchIssues(
  key: string,
  status: IssueStatus,
): Promise<{ items: AdminIssue[]; count: number }> {
  return adminFetch(`/api/v1/admin/issues?status=${status}&limit=50`, key);
}

export function fetchIssue(key: string, id: string): Promise<AdminIssue> {
  return adminFetch(`/api/v1/admin/issues/${encodeURIComponent(id)}`, key);
}

export function createIssue(
  key: string,
  body?: {
    title?: string;
    columnist_id?: string | null;
    category?: string | null;
  },
): Promise<AdminIssue> {
  return adminFetch("/api/v1/admin/issues", key, {
    method: "POST",
    body: JSON.stringify(body || {}),
  });
}

export function updateIssue(
  key: string,
  id: string,
  body: AdminIssueUpdate,
): Promise<AdminIssue> {
  return adminFetch(`/api/v1/admin/issues/${encodeURIComponent(id)}`, key, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function uploadIssueImage(
  key: string,
  id: string,
  file: File,
): Promise<AdminIssue> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(
    `${API_BASE_URL}/api/v1/admin/issues/${encodeURIComponent(id)}/image`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Admin-Key": key,
      },
      body: form,
    },
  );
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as AdminIssue;
}

/** Inline column image — does not replace cover image_url. */
export async function uploadColumnMedia(
  key: string,
  id: string,
  file: File,
): Promise<{ url: string }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(
    `${API_BASE_URL}/api/v1/admin/issues/${encodeURIComponent(id)}/column-media`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Admin-Key": key,
      },
      body: form,
    },
  );
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as { url: string };
}

export function publishIssue(key: string, id: string): Promise<AdminIssue> {
  return adminFetch(`/api/v1/admin/issues/${encodeURIComponent(id)}/publish`, key, {
    method: "POST",
    body: "{}",
  });
}

export function unpublishIssue(key: string, id: string): Promise<AdminIssue> {
  return adminFetch(
    `/api/v1/admin/issues/${encodeURIComponent(id)}/unpublish`,
    key,
    { method: "POST", body: "{}" },
  );
}

export function rejectIssue(
  key: string,
  id: string,
  reason?: string,
): Promise<AdminIssue> {
  return adminFetch(`/api/v1/admin/issues/${encodeURIComponent(id)}/reject`, key, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
  });
}

/* —— Contributor moderation (Phase 4) —— */

export type ApplicationStatus = "PENDING" | "APPROVED" | "REJECTED";

export type TakeModStatus =
  | "draft"
  | "pending_review"
  | "published"
  | "rejected";

export type ContributorApplication = {
  id: string;
  user_id: string;
  motivation: string;
  interests: string;
  sample_text: string;
  status: string;
  admin_note?: string | null;
  created_at: string;
  updated_at: string;
  reviewed_at?: string | null;
  contributor_status: string;
};

export type AdminTake = {
  id: string;
  issue_id: string;
  author_id: string;
  display_name?: string | null;
  title: string;
  body: string;
  source_urls: string[];
  status: string;
  view_count: number;
  reaction_count: number;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
  admin_note?: string | null;
};

export function fetchContributorApplications(
  key: string,
  status: ApplicationStatus = "PENDING",
): Promise<{ items: ContributorApplication[]; count: number }> {
  return adminFetch(
    `/api/v1/admin/contributor/applications?status=${status}&limit=50`,
    key,
  );
}

export function approveContributorApplication(
  key: string,
  id: string,
): Promise<ContributorApplication> {
  return adminFetch(
    `/api/v1/admin/contributor/applications/${encodeURIComponent(id)}/approve`,
    key,
    { method: "POST", body: "{}" },
  );
}

export function rejectContributorApplication(
  key: string,
  id: string,
  reason?: string,
): Promise<ContributorApplication> {
  return adminFetch(
    `/api/v1/admin/contributor/applications/${encodeURIComponent(id)}/reject`,
    key,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    },
  );
}

/** Revoke writing rights: APPROVED → SUSPENDED. */
export function suspendContributorApplication(
  key: string,
  id: string,
  reason?: string,
): Promise<ContributorApplication> {
  return adminFetch(
    `/api/v1/admin/contributor/applications/${encodeURIComponent(id)}/suspend`,
    key,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    },
  );
}

/** Restore writing rights: SUSPENDED → APPROVED. */
export function reinstateContributorApplication(
  key: string,
  id: string,
): Promise<ContributorApplication> {
  return adminFetch(
    `/api/v1/admin/contributor/applications/${encodeURIComponent(id)}/reinstate`,
    key,
    { method: "POST", body: "{}" },
  );
}

export function fetchContributorTakes(
  key: string,
  status: TakeModStatus = "pending_review",
): Promise<{ items: AdminTake[]; count: number }> {
  return adminFetch(
    `/api/v1/admin/contributor/takes?status=${status}&limit=50`,
    key,
  );
}

export function publishContributorTake(
  key: string,
  id: string,
): Promise<AdminTake> {
  return adminFetch(
    `/api/v1/admin/contributor/takes/${encodeURIComponent(id)}/publish`,
    key,
    { method: "POST", body: "{}" },
  );
}

export function rejectContributorTake(
  key: string,
  id: string,
  reason?: string,
): Promise<AdminTake> {
  return adminFetch(
    `/api/v1/admin/contributor/takes/${encodeURIComponent(id)}/reject`,
    key,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    },
  );
}

export type ColumnistStatus = "active" | "archived";

export type AdminColumnist = {
  id: string;
  display_name: string;
  headline: string;
  bio: string;
  specialties?: string[];
  contact_email?: string | null;
  show_email?: boolean;
  profile_public?: boolean;
  image_url: string | null;
  status: ColumnistStatus;
  sort_order: number;
  created_at?: string | null;
};

export function fetchColumnists(
  key: string,
  status?: ColumnistStatus,
): Promise<{ items: AdminColumnist[]; count: number }> {
  const q = status ? `?status=${status}` : "";
  return adminFetch(`/api/v1/admin/columnists${q}`, key);
}

export function createColumnist(
  key: string,
  body: {
    display_name: string;
    headline?: string;
    bio?: string;
    specialties?: string[];
    contact_email?: string | null;
    show_email?: boolean;
    profile_public?: boolean;
    image_url?: string | null;
    status?: ColumnistStatus;
  },
): Promise<AdminColumnist> {
  return adminFetch("/api/v1/admin/columnists", key, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateColumnist(
  key: string,
  id: string,
  body: {
    display_name?: string;
    headline?: string;
    bio?: string;
    specialties?: string[];
    contact_email?: string | null;
    show_email?: boolean;
    profile_public?: boolean;
    image_url?: string | null;
    clear_image?: boolean;
    status?: ColumnistStatus;
  },
): Promise<AdminColumnist> {
  return adminFetch(`/api/v1/admin/columnists/${encodeURIComponent(id)}`, key, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function uploadColumnistImage(
  key: string,
  id: string,
  file: File,
): Promise<AdminColumnist> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(
    `${API_BASE_URL}/api/v1/admin/columnists/${encodeURIComponent(id)}/image`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Admin-Key": key,
      },
      body: form,
    },
  );
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as AdminColumnist;
}

export type XIngestConfig = {
  scan_mode: string;
  scan_hours_kst: string;
  scan_window_minutes: number;
  morning_lane: string;
  afternoon_lane: string;
  night_lane: string;
  lanes_per_scan: number;
  max_results: number;
  industries: string;
  accounts_on: string;
  track_accounts: string;
  dynamic_mode: string;
  hot_enabled: boolean;
  hot_interval_minutes: number;
  hot_idle_scans: number;
  hot_max_hours: number;
  hot_reply_spike: number;
  understand_budget: number;
  industry_slot_reserve: boolean;
  usd_per_post: number;
  usd_per_user: number;
  opposite_lane_count: number;
  daily_post_budget: number;
  updated_at: string | null;
};

export type IndustrySearch = {
  industry_key: string;
  label: string;
  enabled: boolean;
  keywords_ko: string;
  keywords_en: string;
  exclude_ko: string;
  exclude_en: string;
  priority: string;
  frequency: string;
  max_results: number | null;
};

export type XIngestStats = {
  days: number;
  posts_fetched: number;
  search_calls: number;
  timeline_calls: number;
  user_lookups: number;
  new_issues: number;
  updates: number;
  estimated_usd: number;
  usd_per_new_issue: number | null;
  korea_posts: number;
  global_posts: number;
  dynamic_queries: number;
  hot_scans: number;
  slots: {
    slot: string;
    posts: number;
    issues: number;
    estimated_usd: number;
    usd_per_issue: number | null;
  }[];
  industries: {
    industry: string;
    label: string;
    posts: number;
    korea_posts: number;
    global_posts: number;
    processed: number;
    issues: number;
    updates: number;
    api_calls: number;
    estimated_usd: number;
    usd_per_issue: number | null;
  }[];
  hot: { industry: string; lane: string; idle: number; until: string | null }[];
  last_slot_key: string | null;
};

export function fetchXIngestConfig(key: string): Promise<XIngestConfig> {
  return adminFetch("/api/v1/admin/x-ingest/config", key);
}

export function saveXIngestConfig(
  key: string,
  body: XIngestConfig,
): Promise<XIngestConfig> {
  return adminFetch("/api/v1/admin/x-ingest/config", key, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function fetchIndustrySearch(key: string): Promise<IndustrySearch[]> {
  return adminFetch("/api/v1/admin/x-ingest/industries", key);
}

export function saveIndustrySearch(
  key: string,
  body: IndustrySearch[],
): Promise<IndustrySearch[]> {
  return adminFetch("/api/v1/admin/x-ingest/industries", key, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function fetchXIngestStats(
  key: string,
  days = 7,
): Promise<XIngestStats> {
  return adminFetch(`/api/v1/admin/x-ingest/stats?days=${days}`, key);
}

/** Backend policy: published → rejected. */
export function unpublishContributorTake(
  key: string,
  id: string,
  reason?: string,
): Promise<AdminTake> {
  return adminFetch(
    `/api/v1/admin/contributor/takes/${encodeURIComponent(id)}/unpublish`,
    key,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    },
  );
}

