"use client";

import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { createContext } from "react";
import { useRouter } from "next/navigation";

import { DICTS, DEFAULT_LANG, dirFor, type Dict, type Lang, tr } from "@/lib/i18n";
import { setClientLang } from "@/lib/lang-client";

interface I18nValue {
  lang: Lang;
  dic: Dict;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  initialLang = DEFAULT_LANG,
  children,
}: {
  initialLang?: Lang;
  children: React.ReactNode;
}) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const router = useRouter();

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dirFor(lang);
  }, [lang]);

  const setLang = useCallback(
    (next: Lang) => {
      setClientLang(next);
      setLangState(next);
      router.refresh();
    },
    [router],
  );

  const value = useMemo<I18nValue>(
    () => ({
      lang,
      dic: DICTS[lang],
      setLang,
      t: (key: string, vars?: Record<string, string | number>) => tr(DICTS[lang], key, vars),
    }),
    [lang, setLang],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}