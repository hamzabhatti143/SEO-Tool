/**
 * Client for the isolated super-admin API (`/api/admin-backend/*`, rewritten
 * to the backend's `/api/admin/*` in next.config.mjs).
 *
 * Fully separate from the regular user session (NextAuth): the admin token is
 * obtained from `/admin/login`, stored in localStorage, and sent as a Bearer
 * token. There is intentionally no overlap with the user auth flow.
 */

const ADMIN_BASE = "/api/admin-backend";
const TOKEN_KEY = "rp_admin_token";

export type Tier = "standard" | "premium";
export type AccountStatus = "active" | "suspended";

export interface Account {
  id: string;
  email: string;
  full_name: string | null;
  plan: Tier;
  status: AccountStatus;
  must_change_password: boolean;
  project_count: number;
  created_at: string;
}

export interface AccountCreateResponse {
  account: Account;
  temporary_password: string;
  emailed: boolean;
}

export interface AdminStats {
  total: number;
  standard: number;
  premium: number;
  active: number;
  suspended: number;
}

// --- Token storage (client-only) ---
export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function setAdminToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAdminToken(): void {
  if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY);
}

export function isAdminAuthed(): boolean {
  return Boolean(getAdminToken());
}

/** Raised on a 401 so callers can redirect to the admin login. */
export class AdminAuthError extends Error {}

async function request<T>(
  path: string,
  init?: RequestInit & { auth?: boolean }
): Promise<T> {
  const { auth = true, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string> | undefined),
  };
  if (auth) {
    const token = getAdminToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${ADMIN_BASE}${path}`, { ...rest, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401) {
      clearAdminToken();
      throw new AdminAuthError(detail);
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const adminApi = {
  async login(username: string, password: string): Promise<void> {
    const data = await request<{ access_token: string }>("/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      auth: false,
    });
    setAdminToken(data.access_token);
  },

  logout: clearAdminToken,

  listAccounts: () => request<Account[]>("/accounts"),
  stats: () => request<AdminStats>("/stats"),

  createAccount: (data: {
    email: string;
    full_name?: string | null;
    plan: Tier;
    password?: string;
    send_email?: boolean;
  }) =>
    request<AccountCreateResponse>("/accounts", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateAccount: (
    id: string,
    data: { full_name?: string | null; plan?: Tier; password?: string }
  ) =>
    request<Account>(`/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  setStatus: (id: string, status: AccountStatus) =>
    request<Account>(`/accounts/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  deleteAccount: (id: string) =>
    request<void>(`/accounts/${id}`, { method: "DELETE" }),
};
