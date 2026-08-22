/**
 * Format an amount given in minor units (centimes) for display.
 * Deterministic on purpose: no Intl, so tests and SSR agree.
 */
export function formatPrice(minor: number, currency = "DZD"): string {
  const symbol = currency === "DZD" ? "DA" : currency;
  const major = minor / 100;
  const negative = major < 0;
  const abs = Math.abs(major);
  const whole = Math.floor(abs);
  const cents = Math.round((abs - whole) * 100);
  const wholeStr = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${negative ? "-" : ""}${wholeStr},${String(cents).padStart(2, "0")} ${symbol}`;
}

export function formatBudgetRange(
  minMinor: number | null,
  maxMinor: number | null,
  currency = "DZD",
): string | null {
  if (minMinor != null && maxMinor != null) {
    return `${formatPrice(minMinor, currency)} – ${formatPrice(maxMinor, currency)}`;
  }
  if (minMinor != null) return `from ${formatPrice(minMinor, currency)}`;
  if (maxMinor != null) return `up to ${formatPrice(maxMinor, currency)}`;
  return null;
}
