"use client";

import { LANG_OPTIONS } from "@/lib/i18n";
import { useI18n } from "@/components/I18nProvider";

export default function LanguageSwitcher({ tone = "light" }: { tone?: "light" | "dark" }) {
  const { lang, setLang, t } = useI18n();
  const active = tone === "dark"
    ? "border-zaro-ivory/60 text-zaro-ivory"
    : "border-zaro-bronze bg-zaro-bronze/10 text-zaro-bronze-dark";
  const idle = tone === "dark"
    ? "border-transparent text-zaro-ivory/45 hover:text-zaro-ivory"
    : "border-transparent text-zaro-stone hover:text-zaro-graphite";

  return (
    <div
      role="group"
      aria-label={t("footer.langLabel")}
      className="flex items-center gap-1 rounded-full border border-current/0"
    >
      {LANG_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          title={option.native}
          aria-pressed={lang === option.value}
          onClick={() => setLang(option.value)}
          className={`rounded-full border px-2 py-1 font-mono text-[0.6rem] uppercase tracking-[0.12em] transition-colors ${
            lang === option.value ? active : idle
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}