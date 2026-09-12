import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRODUCT_TYPE,
  PRODUCT_TYPES,
  PRODUCT_TYPE_VALUES,
} from "./product-type";

const CANONICAL_BACKEND_VALUES = [
  "dining_table",
  "coffee_table",
  "chair",
  "shelf",
  "desk",
  "custom_metalwork",
  "other",
] as const;

describe("custom-request product-type contract", () => {
  it("matches the backend CustomRequestSubmit.product_type pattern exactly", () => {
    expect(PRODUCT_TYPE_VALUES).toEqual([...CANONICAL_BACKEND_VALUES]);
  });

  it("contains only values the backend accepts", () => {
    const accepted = new Set<string>(CANONICAL_BACKEND_VALUES);
    for (const value of PRODUCT_TYPE_VALUES) {
      expect(accepted.has(value)).toBe(true);
    }
  });

  it("exposes no value the backend does not accept", () => {
    expect(PRODUCT_TYPE_VALUES.length).toBe(CANONICAL_BACKEND_VALUES.length);
  });

  it("uses a backend-accepted default that is a listed option", () => {
    expect(CANONICAL_BACKEND_VALUES).toContain(DEFAULT_PRODUCT_TYPE);
    expect(PRODUCT_TYPE_VALUES).toContain(DEFAULT_PRODUCT_TYPE);
  });

  it("keeps option values in lockstep with the exported value list", () => {
    expect(PRODUCT_TYPES.map((option) => option.value)).toEqual([
      ...PRODUCT_TYPE_VALUES,
    ]);
  });
});