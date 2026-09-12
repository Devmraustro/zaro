"use client";

/**
 * ZARO admin session handling — browser security contract.
 *
 * Access-token credential: SHORT-LIVED JWT, held in module memory for the
 * lifetime of the page. Cleared on sign-out and never written to
 * localStorage/sessionStorage.
 *
 * Refresh credential: HTTPONLY cookie (zaro_refresh) set by the API on the API
 * origin, scoped to /api/v1/auth. JavaScript never reads or stores it — it is
 * absent from document.cookie, never written to browser storage, and never
 * retained from response bodies (it is deliberately stripped at login).
 *
 * CSRF token: the API writes a readable zaro_csrf cookie on the API origin and
 * additionally returns the same value as csrf_token in the login/refresh JSON
 * bodies. The cookie is path-scoped to /api/v1/auth on a different origin, so
 * page JavaScript cannot read it from document.cookie; the response body is the
 * only reachable source. The value is held in module memory ONLY and echoed in
 * the X-CSRF-Token header on cookie-sourced refresh. It rotates on every
 * login/refresh and is never persisted to browser storage.
 *
 * Session restore (FD-01): the CSRF value is memory-only, so a full page
 * reload clears it. On a cold load the client calls GET /auth/session -- a
 * read-only API probe that, when the HttpOnly refresh cookie is live, returns
 * a fresh CSRF double-submit value (and re-sets the readable zaro_csrf cookie
 * on the API origin). The SPA then runs the normal single-flight, rotating
 * refresh to mint a short-lived access token. The probe itself issues no token
 * and never rotates or revokes the refresh credential, so reloads cannot trip
 * the backend reuse-detection family revocation. If no live cookie session
 * exists the probe reports session_active=false and the user is sent to the
 * sign-in form.
 */

import type { LoginResponse, TokenResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001/api/v1";

/** Short-lived access token. Runtime memory only — never persisted. */
let accessToken: string | null = null;

/**
 * CSRF double-submit value delivered in login/refresh JSON bodies (mirror of
 * the API-origin zaro_csrf cookie). Runtime memory only — never persisted.
 */
let csrfToken: string | null = null;

/**
 * Single-flight refresh: at most one refresh request is in flight at any time.
 * Concurrent 401s share this promise. This is also what keeps the backend's
 * rotation safe — a single parallel refresh would replay the already-rotated
 * credential and trip the reuse-detection family revocation.
 */
let refreshPromise: Promise<string | null> | null = null;

export class AuthError extends Error {
  code: "login_failed" | "session_expired" | "not_signed_in";

  constructor(message: string, code: AuthError["code"]) {
    super(message);
    this.name = "AuthError";
    this.code = code;
  }
}

/** Internal marker for "access token rejected with 401" so adminFetch can retry exactly once. */
class Unauthorized extends Error {
  response: Response;

  constructor(response: Response) {
    super("unauthorized");
    this.response = response;
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

function clearAuthState(): void {
  accessToken = null;
  csrfToken = null;
}

export type AdminLoginResult = Omit<LoginResponse, "refresh_token" | "csrf_token">;

/**
 * Authenticate with the API. The login response body contains a refresh
 * credential, but it is deliberately IGNORED here: the browser receives the
 * HttpOnly zaro_refresh cookie directly, and only the access token is retained
 * in memory. The response's csrf_token is kept in memory only — it belongs to
 * the X-CSRF-Token header, never to callers or storage.
 * credentials: "include" is required so the browser stores and sends the auth
 * cookies.
 */
export async function login(email: string, password: string): Promise<AdminLoginResult> {
  clearAuthState();
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new AuthError(body?.error?.message ?? "Sign in failed", "login_failed");
  }
  const data = (await response.json()) as LoginResponse;
  // Access token → memory; CSRF double-submit value → memory only for the
  // X-CSRF-Token header; refresh credential → stays exclusively in the cookie.
  accessToken = data.access_token;
  csrfToken = data.csrf_token;
  const { access_token, expires_in, token_type, user } = data;
  return { access_token, expires_in, token_type, user };
}

async function performRefresh(): Promise<string | null> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (csrfToken !== null) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers,
    });
  } catch {
    // Network failure: do not destroy a possibly-valid session.
    return null;
  }

  if (response.status === 401 || response.status === 403) {
    // Refresh cookie absent/invalid or CSRF rejected: session is gone.
    clearAuthState();
    return null;
  }
  if (!response.ok) {
    return null;
  }
  const data = (await response.json()) as TokenResponse;
  // The rotated refresh credential stays in the (re-set) HttpOnly cookie; only
  // the new access token and the freshly rotated CSRF value enter memory.
  accessToken = data.access_token;
  csrfToken = data.csrf_token;
  return accessToken;
}

/** Single-flight refresh. Resolves to the new access token, or null on failure. */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/**
 * Cold-load session probe. GET /auth/session is read-only: when the HttpOnly
 * refresh cookie is live it returns a fresh CSRF double-submit value (memory-only
 * here, never stored). It does not mint an access token and does not rotate the
 * refresh credential, so a reload can never trip reuse detection. When no live
 * cookie session exists it reports session_active=false and no probe value is
 * retained. A network failure is treated as "no session" without destroying
 * anything.
 */
async function bootstrapSession(): Promise<boolean> {
  if (accessToken !== null || csrfToken !== null) return true;
  try {
    const response = await fetch(`${API_BASE}/auth/session`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { session_active?: boolean; csrf_token?: string | null };
    if (data.session_active !== true || typeof data.csrf_token !== "string") return false;
    csrfToken = data.csrf_token;
    return true;
  } catch {
    return false;
  }
}

/**
 * True when a live browser session exists in memory, or can still be re-earned
 * via the cookie: cold page loads bootstrap the CSRF value from GET /auth/session
 * and then refresh single-flight. Never stores anything to browser storage.
 */
export async function hasActiveSession(): Promise<boolean> {
  if (accessToken !== null) return true;
  if (csrfToken === null && !(await bootstrapSession())) return false;
  const token = await refreshAccessToken();
  return token !== null;
}

async function doAdminFetch<T>(path: string, options: RequestInit, token: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers as Record<string, string>),
    },
  });
  if (response.status === 401) {
    throw new Unauthorized(response);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Authenticated admin API call.
 *
 * - Cold reload path: no in-memory credentials, so the session is bootstrapped
 *   from the HttpOnly cookie via GET /auth/session, then refreshed single-flight.
 * - 401 path: perform exactly ONE coordinated refresh, then retry the original
 *   request once. Concurrent 401s share a single refresh (single-flight).
 * - If refresh fails, memory is cleared and the caller is told to re-login.
 */
export async function adminFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let token = accessToken;
  if (token === null) {
    if (csrfToken === null && !(await bootstrapSession())) {
      throw new AuthError("Not signed in — sign in again", "not_signed_in");
    }
    token = await refreshAccessToken();
    if (token === null) {
      throw new AuthError("Not signed in — sign in again", "not_signed_in");
    }
  }

  try {
    return await doAdminFetch<T>(path, options, token);
  } catch (err) {
    if (err instanceof Unauthorized) {
      const fresh = await refreshAccessToken();
      if (fresh === null) {
        throw new AuthError("Session expired — sign in again", "session_expired");
      }
      try {
        return await doAdminFetch<T>(path, options, fresh);
      } catch (retryErr) {
        if (retryErr instanceof Unauthorized) {
          // A freshly rotated token was also rejected: the session is gone.
          clearAuthState();
          throw new AuthError("Session expired — sign in again", "session_expired");
        }
        throw retryErr;
      }
    }
    throw err;
  }
}

/**
 * Sign out: revoke the server-side session (refresh rotation family) through
 * /auth/logout, then clear all in-memory auth state. Server revocation is
 * best-effort so local cleanup never blocks on the network. The CSRF value
 * accompanies the logout request when available (the backend only requires the
 * Bearer token; the extra header is harmless).
 */
export async function logout(): Promise<void> {
  let token = accessToken;
  if (token === null && csrfToken !== null) {
    // If the access token expired but the refresh cookie is still valid,
    // rotate once so logout can present a live access token to the API.
    await refreshAccessToken();
    token = accessToken;
  }
  if (token !== null) {
    const headers: Record<string, string> = {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    };
    if (csrfToken !== null) {
      headers["X-CSRF-Token"] = csrfToken;
    }
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers,
      });
    } catch {
      // Best effort: a network failure must not block local cleanup.
    }
  }
  clearAuthState();
}