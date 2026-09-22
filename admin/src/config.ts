/** Admin portal config — never commit real keys. */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export const ADMIN_KEY_STORAGE = "issue_admin_key";
