import { cookies } from "next/headers";

import { DEFAULT_LANG, LANG_COOKIE, isLang, type Lang } from "@/lib/i18n";

/** Server Component only: resolve the active language from the request cookie. */
export async function getServerLang(): Promise<Lang> {
  const store = await cookies();
  const value = store.get(LANG_COOKIE)?.value;
  return isLang(value) ? value : DEFAULT_LANG;
}