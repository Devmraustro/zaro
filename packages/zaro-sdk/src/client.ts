import type {
  ErrorResponse,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  TokenResponse,
} from "./types.js";
import {
  AuthenticationError,
  ForbiddenError,
  NotFoundError,
  ValidationError,
  ZaroError,
} from "./errors.js";

export interface ZaroClientConfig {
  baseUrl: string;
  timeout?: number;
}

export class ZaroClient {
  private readonly baseUrl: string;
  private readonly timeout: number;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor(config: ZaroClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.timeout = config.timeout ?? 30_000;
  }

  setTokens(accessToken: string, refreshToken: string): void {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
  }

  // --- Health -----------------------------------------------------------

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/api/v1/health");
  }

  async liveness(): Promise<{ status: string }> {
    return this.request<{ status: string }>("GET", "/health/live");
  }

  // --- Auth -------------------------------------------------------------

  async login(data: LoginRequest): Promise<LoginResponse> {
    const response = await this.request<LoginResponse>("POST", "/api/v1/auth/login", data);
    this.setTokens(response.access_token, response.refresh_token);
    return response;
  }

  async refreshAccessToken(): Promise<TokenResponse> {
    if (!this.refreshToken) {
      throw new AuthenticationError("No refresh token available");
    }
    const response = await this.request<TokenResponse>("POST", "/api/v1/auth/refresh", {
      refresh_token: this.refreshToken,
    });
    this.setTokens(response.access_token, response.refresh_token);
    return response;
  }

  async logout(): Promise<void> {
    if (this.refreshToken) {
      await this.request<void>("POST", "/api/v1/auth/logout", { refresh_token: this.refreshToken });
    }
    this.clearTokens();
  }

  // --- Internal ---------------------------------------------------------

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };

    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorBody = (await response.json().catch(() => null)) as ErrorResponse | null;
        const message = errorBody?.error?.message ?? `HTTP ${response.status}`;
        const code = errorBody?.error?.code ?? "http_error";
        const details = errorBody?.error?.details;

        switch (response.status) {
          case 401:
            throw new AuthenticationError(message);
          case 403:
            throw new ForbiddenError(message);
          case 404:
            throw new NotFoundError(message);
          case 422:
            throw new ValidationError(message, details);
          default:
            throw new ZaroError(message, code, response.status, details);
        }
      }

      if (response.status === 204) {
        return undefined as T;
      }

      return (await response.json()) as T;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
