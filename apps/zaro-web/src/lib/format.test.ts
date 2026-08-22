import { describe, expect, it } from "vitest";
import { formatBudgetRange, formatPrice } from "./format";

describe("formatPrice", () => {
  it("formats minor units as major units with DA suffix", () => {
    expect(formatPrice(1250000)).toBe("12 500,00 DA");
  });

  it("keeps cents", () => {
    expect(formatPrice(12345)).toBe("123,45 DA");
  });

  it("pads single-digit cents", () => {
    expect(formatPrice(1005)).toBe("10,05 DA");
  });

  it("handles zero", () => {
    expect(formatPrice(0)).toBe("0,00 DA");
  });

  it("groups thousands with spaces", () => {
    expect(formatPrice(123456789)).toBe("1 234 567,89 DA");
  });

  it("uses raw code for non-DZD currencies", () => {
    expect(formatPrice(5000, "EUR")).toBe("50,00 EUR");
  });

  it("handles negative amounts", () => {
    expect(formatPrice(-25050)).toBe("-250,50 DA");
  });
});

describe("formatBudgetRange", () => {
  it("joins min and max", () => {
    expect(formatBudgetRange(100000, 200000)).toBe("1 000,00 DA – 2 000,00 DA");
  });

  it("handles open lower bound", () => {
    expect(formatBudgetRange(null, 200000)).toBe("up to 2 000,00 DA");
  });

  it("handles open upper bound", () => {
    expect(formatBudgetRange(100000, null)).toBe("from 1 000,00 DA");
  });

  it("returns null when no bounds", () => {
    expect(formatBudgetRange(null, null)).toBeNull();
  });
});
