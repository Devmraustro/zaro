import { describe, it, expect } from "vitest";
import { ZaroClient } from "../src/client.js";
import { AuthenticationError, ZaroError } from "../src/errors.js";

describe("ZaroClient", () => {
  it("constructs with base URL", () => {
    const client = new ZaroClient({ baseUrl: "http://localhost:8001" });
    expect(client).toBeDefined();
  });

  it("strips trailing slash from base URL", () => {
    const client = new ZaroClient({ baseUrl: "http://localhost:8001/" });
    expect(client).toBeDefined();
  });

  it("manages tokens", () => {
    const client = new ZaroClient({ baseUrl: "http://localhost:8001" });
    client.setTokens("access-123", "refresh-456");
    client.clearTokens();
  });
});

describe("ZaroError", () => {
  it("creates error with properties", () => {
    const error = new ZaroError("test message", "test_code", 400, { extra: "data" });
    expect(error.message).toBe("test message");
    expect(error.code).toBe("test_code");
    expect(error.statusCode).toBe(400);
    expect(error.details).toEqual({ extra: "data" });
    expect(error.name).toBe("ZaroError");
  });
});

describe("AuthenticationError", () => {
  it("creates auth error with defaults", () => {
    const error = new AuthenticationError();
    expect(error.message).toBe("Authentication required");
    expect(error.statusCode).toBe(401);
    expect(error.name).toBe("AuthenticationError");
  });
});
