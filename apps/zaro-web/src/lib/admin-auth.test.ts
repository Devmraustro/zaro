import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";

/**
 * Security tests for the browser admin session contract.
 *
 * Invariants under test:
 *  1. login does not persist refresh_token, csrf_token, or any token to browser storage
 *  2. login uses credentials: "include"
 *  3. login returns neither the refresh token nor the CSRF token to callers
 *  4. refresh uses credentials: "include" and echoes the in-memory csrf_token
 *     (from the login/refresh response, not document.cookie) in X-CSRF-Token
 *  5. refresh without a known csrf_token omits the header
 *  6. a refreshed access token replaces the in-memory token; csrf rotates
 *  7. a 401 triggers exactly one refresh, then one retry
 *  8. concurrent 401s share a single refresh (single-flight)
 *  9. refresh failure clears access and CSRF memory and forces re-auth
 * 10. a cold reload (no in-memory CSRF) cannot silently restore the session
 * 11. logout reaches the backend with the bearer token and CSRF header
 * 12. auth tokens and csrf are never written to localStorage/sessionStorage
 */

const loginBody = {
  access_token: "at-1",
  refresh_token: "rt-1",
  token_type: "bearer",
  expires_in: 1800,
  csrf_token: "csrf-c1",
  user: { id: "u1", email: "ops@example.com", full_name: "Ops", role: "admin", is_active: true },
};

const refreshBody = {
  access_token: "at-2",
  refresh_token: "rt-2",
  token_type: "bearer",
  expires_in: 1800,
  csrf_token: "csrf-c2",
};

const unauthorizedBody = { error: { code: "unauthorized", message: "Invalid or expired token" } };

type FakeResponse = {
  status: number;
  ok: boolean;
  json: () => Promise<unknown>;
};

function jsonResponse(status: number, data: unknown): FakeResponse {
  return { status, ok: status >= 200 && status < 300, json: async () => data };
}

type CallInit = {
  method?: string;
  credentials?: string;
  headers?: Record<string, string>;
  body?: string;
};

function lastCall(mock: Mock, index: number) {
  const [url, init] = mock.mock.calls[index] as [string, CallInit];
  return { url, init };
}

function callsFor(mock: Mock, fragment: string): { url: string; init: CallInit }[] {
  return mock.mock.calls
    .filter((call) => String(call[0]).includes(fragment))
    .map((call) => call as [string, CallInit])
    .map(([url, init]) => ({ url, init }));
}

async function loadAuth() {
  vi.resetModules();
  return import("@/lib/admin-auth");
}

describe("admin auth security", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    (window as unknown as { localStorage: Storage }).localStorage.clear();
    (window as unknown as { sessionStorage: Storage }).sessionStorage.clear();
  });

  it("login stores no auth tokens or csrf in localStorage or sessionStorage", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, loginBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");

    expect((window as unknown as { localStorage: Storage }).localStorage.length).toBe(0);
    expect((window as unknown as { sessionStorage: Storage }).sessionStorage.length).toBe(0);
    expect(auth.getAccessToken()).toBe("at-1");
  });

  it("login uses credentials: include and posts to /auth/login", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, loginBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");

    const { url, init } = lastCall(fetchMock, 0);
    expect(url).toMatch(/\/auth\/login$/);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body ?? "{}")).toEqual({ email: "ops@example.com", password: "password-1" });
  });

  it("login exposes neither the refresh token nor the csrf token to callers", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, loginBody) as Response);
    const auth = await loadAuth();

    const result = await auth.login("ops@example.com", "password-1");

    expect("refresh_token" in result).toBe(false);
    expect("csrf_token" in result).toBe(false);
    expect(result.access_token).toBe("at-1");
  });

  it("refresh uses credentials: include and sends the response-provided csrf_token in X-CSRF-Token", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    const token = await auth.refreshAccessToken();

    expect(token).toBe("at-2");
    const { url, init } = callsFor(fetchMock, "/auth/refresh")[0]!;
    expect(url).toMatch(/\/auth\/refresh$/);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(init.headers?.["X-CSRF-Token"]).toBe("csrf-c1");
    expect(init.headers?.["Content-Type"]).toBeUndefined();
  });

  it("refresh omits the CSRF header when no csrf_token is known", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response);
    const auth = await loadAuth();

    await auth.refreshAccessToken();

    const { init } = lastCall(fetchMock, 0);
    expect(init.headers?.["X-CSRF-Token"]).toBeUndefined();
  });

  it("a refreshed access token replaces the in-memory token and rotates the CSRF value", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    expect(auth.getAccessToken()).toBe("at-1");

    await auth.refreshAccessToken();
    expect(auth.getAccessToken()).toBe("at-2");
    expect(callsFor(fetchMock, "/auth/refresh")[0]!.init.headers?.["X-CSRF-Token"]).toBe("csrf-c1");

    // The rotated csrf from the refresh response feeds the next refresh.
    await auth.refreshAccessToken();
    expect(callsFor(fetchMock, "/auth/refresh")[1]!.init.headers?.["X-CSRF-Token"]).toBe("csrf-c2");
  });

  it("a 401 triggers exactly one refresh and retries the original request once", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, { items: [] }) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    const data = await auth.adminFetch<{ items: unknown[] }>("/admin/products");

    expect(data.items).toEqual([]);
    expect(callsFor(fetchMock, "/auth/refresh")).toHaveLength(1);
    const retry = lastCall(fetchMock, 3);
    expect(retry.url).toMatch(/\/admin\/products/);
    expect(retry.init.headers?.["Authorization"]).toBe("Bearer at-2");
  });

  it("concurrent 401s share a single refresh request", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, { items: ["a"] }) as Response)
      .mockResolvedValueOnce(jsonResponse(200, { items: ["b"] }) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    const [resultA, resultB] = await Promise.all([
      auth.adminFetch<{ items: string[] }>("/admin/a"),
      auth.adminFetch<{ items: string[] }>("/admin/b"),
    ]);

    expect(resultA.items).toEqual(["a"]);
    expect(resultB.items).toEqual(["b"]);
    expect(callsFor(fetchMock, "/auth/refresh")).toHaveLength(1);
  });

  it("does not retry a second refresh when the retried request 401s again", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response)
      .mockResolvedValueOnce(jsonResponse(200, refreshBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    await expect(auth.adminFetch("/admin/products")).rejects.toMatchObject({ code: "session_expired" });
    expect(callsFor(fetchMock, "/auth/refresh")).toHaveLength(1);
    expect(auth.getAccessToken()).toBeNull();
  });

  it("a failed refresh clears access and CSRF memory and reports the session as expired", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response)
      .mockResolvedValueOnce(jsonResponse(401, unauthorizedBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    await expect(auth.adminFetch("/admin/products")).rejects.toMatchObject({ code: "session_expired" });
    expect(auth.getAccessToken()).toBeNull();

    // CSRF memory is cleared too: a subsequent refresh sends no header.
    await auth.refreshAccessToken();
    const { init } = callsFor(fetchMock, "/auth/refresh")[1]!;
    expect(init.headers?.["X-CSRF-Token"]).toBeUndefined();
  });

  it("a cold reload cannot silently restore the session (no in-memory CSRF value)", async () => {
    const fetchMock = vi.mocked(fetch);
    const auth = await loadAuth();

    await expect(auth.adminFetch("/admin/products")).rejects.toMatchObject({ code: "not_signed_in" });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(auth.getAccessToken()).toBeNull();
  });

  it("hasActiveSession is true while the access token is in memory", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, loginBody) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    await expect(auth.hasActiveSession()).resolves.toBe(true);
    expect(callsFor(fetchMock, "/auth/refresh")).toHaveLength(0);
  });

  it("hasActiveSession is false on a cold reload without attempting a refresh", async () => {
    const fetchMock = vi.mocked(fetch);
    const auth = await loadAuth();

    await expect(auth.hasActiveSession()).resolves.toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logout POSTs to /auth/logout with the bearer token and CSRF header, then clears memory", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, loginBody) as Response)
      .mockResolvedValueOnce(jsonResponse(204, null) as Response);
    const auth = await loadAuth();

    await auth.login("ops@example.com", "password-1");
    await auth.logout();

    const { url, init } = lastCall(fetchMock, 1);
    expect(url).toMatch(/\/auth\/logout$/);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(init.headers?.["Authorization"]).toBe("Bearer at-1");
    expect(init.headers?.["X-CSRF-Token"]).toBe("csrf-c1");
    expect(auth.getAccessToken()).toBeNull();
    expect((window as unknown as { localStorage: Storage }).localStorage.length).toBe(0);
    expect((window as unknown as { sessionStorage: Storage }).sessionStorage.length).toBe(0);
  });

  it("logout performs no network calls on a cold reload and still clears memory", async () => {
    const fetchMock = vi.mocked(fetch);
    const auth = await loadAuth();

    await auth.logout();

    expect(fetchMock).not.toHaveBeenCalled();
    expect(auth.getAccessToken()).toBeNull();
  });
});