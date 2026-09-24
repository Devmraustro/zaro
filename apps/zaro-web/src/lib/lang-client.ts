import { DEFAULT_LANG, LANG_COOKIE, isLang, type Lang } from "@/lib/i18n";

const STORAGE_KEY = "zaro_lang";

/** Client-only: resolve the active language (localStorage, then cookie, then default). */
export function getClientLang(): Lang {
  if (typeof window === "undefined") return DEFAULT_LANG;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch {
    /* ignore storage errors */
  }
  const match = document.cookie.split(";").map((c) => c.trim()).find((c) => c.startsWith(`${LANG_COOKIE}=`));
  if (match) {
    const value = match.slice(LANG_COOKIE.length + 1);
    if (isLang(value)) return value;
  }
  return DEFAULT_LANG;
}

/** Client-only: persist the active language and mirror it in a cookie for SSR. */
export function setClientLang(lang: Lang): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* ignore storage errors */
  }
  document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=31536000; SameSite=Lax`;
}