"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/components/I18nProvider";
import type { TrackResult } from "@/types/api";
import type { ProductType } from "@/types/product-type";

const fieldClass =
  "w-full border-b border-zaro-graphite/15 bg-transparent px-0.5 py-2.5 text-sm text-zaro-graphite outline-none transition-colors placeholder:text-zaro-stone focus:border-zaro-bronze";

const labelClass = "mb-2 block text-[0.65rem] font-medium uppercase tracking-[0.18em] text-zaro-stone";

const STATUS_ORDER = [
  "submitted",
  "under_review",
  "needs_information",
  "quotation_pending",
  "converted",
  "cancelled",
] as const;

function presentIndex(status: string): number {
  const pos = STATUS_ORDER.indexOf(status as (typeof STATUS_ORDER)[number]);
  return pos === -1 ? -1 : Math.min(pos, STATUS_ORDER.length - 1);
}

const PRODUCT_TYPE_KEY: Record<ProductType, string> = {
  dining_table: "form.ptDiningTable",
  coffee_table: "form.ptCoffeeTable",
  chair: "form.ptChair",
  shelf: "form.ptShelf",
  desk: "form.ptDesk",
  custom_metalwork: "form.ptMetalwork",
  other: "form.ptOther",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function TrackingLookup() {
  const { t } = useI18n();
  const [reference, setReference] = useState("");
  const [contact, setContact] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TrackResult | null>(null);

  const productTypeKey = (value: string) =>
    PRODUCT_TYPE_KEY[value as ProductType] ?? "form.ptOther";

  const statusKey = (status: string, suffix = "") =>
    `track.st${suffix}.${status}`;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ref = reference.trim().toUpperCase();
    const value = contact.trim();
    if (ref.length < 3 || !value) {
      setError(t("track.errorRequire"));
      return;
    }
    setError(null);
    setChecking(true);
    // The API accepts email or phone; a contact containing "@" is email.
    const contactParam = value.includes("@")
      ? `&email=${encodeURIComponent(value)}`
      : `&phone=${encodeURIComponent(value)}`;
    try {
      const found = await apiFetch<TrackResult>(
        `/custom-requests/track?reference=${encodeURIComponent(ref)}${contactParam}`,
      );
      setResult(found);
    } catch (err) {
      setResult(null);
      const status = err instanceof Error && "status" in err ? Number((err as { status?: unknown }).status) : 0;
      setError(status === 404 ? t("track.notFound") : t("track.errorGeneric"));
    } finally {
      setChecking(false);
    }
  }

  const stepIndex = result ? presentIndex(result.status) : -1;
  const isCancelled = result?.status === "cancelled";

  return (
    <div>
      <form
        onSubmit={handleSubmit}
        className="space-y-6"
        data-testid="tracking-lookup-form"
      >
        <label className="block">
          <span className={labelClass}>{t("track.referenceLabel")}</span>
          <input
            value={reference}
            onChange={(event) => setReference(event.target.value)}
            minLength={3}
            maxLength={20}
            autoComplete="off"
            className={fieldClass}
            placeholder={t("track.referencePlaceholder")}
          />
        </label>
        <label className="block">
          <span className={labelClass}>{t("track.contactLabel")}</span>
          <input
            value={contact}
            onChange={(event) => setContact(event.target.value)}
            maxLength={320}
            autoComplete="off"
            className={fieldClass}
            placeholder={t("track.contactPlaceholder")}
          />
        </label>

        {error && (
          <div role="alert" className="border border-red-300/60 bg-red-50/50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={checking}
          className="w-full bg-zaro-black px-10 py-3.5 text-[0.72rem] font-medium uppercase tracking-[0.18em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft disabled:opacity-50"
        >
          {checking ? t("track.checking") : t("track.lookup")}
        </button>
      </form>

      {result && (
        <div
          className="grain mt-12 border border-zaro-bronze/30 bg-zaro-paper p-8"
          data-testid="tracking-result"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-zaro-graphite/10 pb-5">
            <p className="text-[0.65rem] font-medium uppercase tracking-[0.2em] text-zaro-stone">
              {t("track.referenceLabel2")} · {result.reference}
            </p>
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-zaro-bronze-dark">
              {t(statusKey(result.status))}
            </p>
          </div>

          <ol className="mt-7 space-y-0">
            {STATUS_ORDER.map((step, index) => {
              const reached = stepIndex !== -1 && index <= stepIndex;
              const shown = reached || step === "cancelled" || isCancelled;
              if (!shown) return null;
              return (
                <li key={step} className="relative flex gap-4 pb-6 last:pb-0">
                  <div className="flex flex-col items-center">
                    <span
                      className={`mt-0.5 size-2.5 rounded-full ${
                        reached ? "bg-zaro-bronze" : "bg-zaro-graphite/25"
                      }`}
                      aria-hidden="true"
                    />
                    {index < STATUS_ORDER.length - 1 && (
                      <span className="mt-1 w-px flex-1 bg-zaro-graphite/15" aria-hidden="true" />
                    )}
                  </div>
                  <div className="pt-0">
                    <h3
                      className={`text-sm font-medium ${
                        reached ? "text-zaro-black" : "text-zaro-stone"
                      }`}
                    >
                      {t(statusKey(step))}
                    </h3>
                    <p className="mt-1 text-xs leading-relaxed text-zaro-steel">
                      {t(statusKey(step, "Copy"))}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>

          <dl className="mt-7 grid grid-cols-1 gap-x-8 gap-y-4 border-t border-zaro-graphite/10 pt-6 sm:grid-cols-3">
            <div>
              <dt className="text-[0.62rem] font-medium uppercase tracking-[0.18em] text-zaro-stone">
                {t("track.productTypeLabel")}
              </dt>
              <dd className="mt-1 text-sm text-zaro-graphite">{t(productTypeKey(result.product_type))}</dd>
            </div>
            <div>
              <dt className="text-[0.62rem] font-medium uppercase tracking-[0.18em] text-zaro-stone">
                {t("track.submittedLabel")}
              </dt>
              <dd className="mt-1 text-sm text-zaro-graphite">{formatDate(result.created_at)}</dd>
            </div>
            <div>
              <dt className="text-[0.62rem] font-medium uppercase tracking-[0.18em] text-zaro-stone">
                {t("track.updatedLabel")}
              </dt>
              <dd className="mt-1 text-sm text-zaro-graphite">{formatDate(result.updated_at)}</dd>
            </div>
          </dl>

          <p className="mt-7 text-xs text-zaro-stone">{t("track.helpLine")}</p>
        </div>
      )}
    </div>
  );
}