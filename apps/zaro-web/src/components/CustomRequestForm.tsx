"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { CustomRequestPublic, CustomRequestSubmit } from "@/types/api";
import {
  DEFAULT_PRODUCT_TYPE,
  PRODUCT_TYPES,
  type ProductType,
} from "@/types/product-type";

const fieldClass =
  "w-full border-b border-zaro-graphite/15 bg-transparent px-0.5 py-2.5 text-sm text-zaro-graphite outline-none transition-colors placeholder:text-zaro-stone focus:border-zaro-bronze";

const labelClass = "mb-2 block text-[0.65rem] font-medium uppercase tracking-[0.18em] text-zaro-stone";

function FieldsetHeading({ number, children }: { number: string; children: React.ReactNode }) {
  return (
    <h3 className="flex items-center gap-3 pt-2 font-serif text-lg font-medium text-zaro-black">
      <span className="font-mono text-[0.625rem] uppercase tracking-[0.18em] text-zaro-bronze-dark">{number}</span>
      {children}
    </h3>
  );
}

export default function CustomRequestForm() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CustomRequestPublic | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    // Browsers block invalid submits before this handler runs; jsdom does not.
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }
    setError(null);
    setSubmitting(true);
    const fd = new FormData(form);

    const description = String(fd.get("description") ?? "").trim();
    if (description.length < 10) {
      // Native minLength is not enforced by jsdom; mirror the API rule here.
      setSubmitting(false);
      setError("Please describe your project in at least 10 characters.");
      return;
    }

    const budgetMin = String(fd.get("budget_min") ?? "").trim();
    const budgetMax = String(fd.get("budget_max") ?? "").trim();
    const toMinor = (value: string) =>
      value ? Math.round(parseFloat(value.replace(",", ".")) * 100) : null;

    const payload: CustomRequestSubmit = {
      full_name: String(fd.get("full_name") ?? "").trim(),
      email: String(fd.get("email") ?? "").trim() || null,
      phone: String(fd.get("phone") ?? "").trim() || null,
      product_type: String(fd.get("product_type") ?? DEFAULT_PRODUCT_TYPE) as ProductType,
      description,
      desired_dimensions: String(fd.get("desired_dimensions") ?? "").trim() || null,
      materials: String(fd.get("materials") ?? "").trim() || null,
      colors: String(fd.get("colors") ?? "").trim() || null,
      finish: String(fd.get("finish") ?? "").trim() || null,
      quantity: parseInt(String(fd.get("quantity") ?? "1"), 10) || 1,
      budget_min_minor: budgetMin ? toMinor(budgetMin) : null,
      budget_max_minor: budgetMax ? toMinor(budgetMax) : null,
    };

    try {
      const created = await apiFetch<CustomRequestPublic>("/custom-requests", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(created);
      form.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div
        className="grain flex flex-col items-center border border-zaro-bronze/30 bg-zaro-paper px-8 py-14 text-center"
        data-testid="request-success"
      >
        <span className="h-px w-12 bg-zaro-bronze" aria-hidden="true" />
        <h2 className="mt-6 font-serif text-2xl font-medium text-zaro-black">Request received</h2>
        <p className="mt-3 max-w-sm text-sm leading-relaxed text-zaro-steel">
          Your reference is{" "}
          <span className="font-mono font-semibold text-zaro-bronze-dark">{result.reference}</span>. A
          member of the studio will review it and reply with next steps.
        </p>
        <button
          type="button"
          onClick={() => setResult(null)}
          className="mt-8 border border-zaro-graphite/20 px-7 py-2.5 text-[0.68rem] uppercase tracking-[0.18em] text-zaro-graphite transition-colors hover:border-zaro-graphite hover:bg-zaro-graphite hover:text-zaro-ivory"
        >
          Submit another request
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-10" data-testid="custom-request-form">
      <div className="space-y-6">
        <FieldsetHeading number="01">About you</FieldsetHeading>
        <div className="grid grid-cols-1 gap-7 sm:grid-cols-2">
          <label className="block">
            <span className={labelClass}>
              Full name <span aria-hidden="true">*</span>
            </span>
            <input name="full_name" required minLength={2} maxLength={200} className={fieldClass} />
          </label>
          <label className="block">
            <span className={labelClass}>Email</span>
            <input name="email" type="email" className={fieldClass} />
          </label>
          <label className="block">
            <span className={labelClass}>Phone</span>
            <input name="phone" className={fieldClass} />
          </label>
          <label className="block">
            <span className={labelClass}>Product type *</span>
            <select name="product_type" required defaultValue={DEFAULT_PRODUCT_TYPE} className={`${fieldClass} cursor-pointer`}>
              {PRODUCT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="space-y-6">
        <FieldsetHeading number="02">Your project</FieldsetHeading>
        <label className="block">
          <span className={labelClass}>
            Describe your project * <span className="normal-case">(min. 10 characters)</span>
          </span>
          <textarea
            name="description"
            required
            minLength={10}
            maxLength={4000}
            rows={5}
            className={`${fieldClass} resize-y leading-relaxed`}
            placeholder="e.g. A 2.4 m oak dining table on a blackened steel base, for a family of six…"
          />
        </label>
        <div className="grid grid-cols-1 gap-7 sm:grid-cols-2">
          <label className="block">
            <span className={labelClass}>Desired dimensions</span>
            <input name="desired_dimensions" placeholder="e.g. 200 × 90 × 75 cm" className={fieldClass} />
          </label>
          <label className="block">
            <span className={labelClass}>Quantity</span>
            <input name="quantity" type="number" min={1} max={1000} defaultValue={1} className={fieldClass} />
          </label>
        </div>
      </div>

      <div className="space-y-6">
        <FieldsetHeading number="03">Materials & budget</FieldsetHeading>
        <div className="grid grid-cols-1 gap-7 sm:grid-cols-3">
          <label className="block">
            <span className={labelClass}>Materials</span>
            <input name="materials" placeholder="e.g. solid oak, blackened steel" className={fieldClass} />
          </label>
          <label className="block">
            <span className={labelClass}>Colors</span>
            <input name="colors" className={fieldClass} />
          </label>
          <label className="block">
            <span className={labelClass}>Finish</span>
            <input name="finish" className={fieldClass} />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-5">
          <label className="block">
            <span className={labelClass}>Budget min (DA)</span>
            <input name="budget_min" inputMode="decimal" className={fieldClass} placeholder="0" />
          </label>
          <label className="block">
            <span className={labelClass}>Budget max (DA)</span>
            <input name="budget_max" inputMode="decimal" className={fieldClass} placeholder="0" />
          </label>
        </div>
      </div>

      {error && (
        <div role="alert" className="border border-red-300/60 bg-red-50/50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex flex-col items-start gap-3 border-t border-zaro-graphite/10 pt-8">
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-zaro-black px-10 py-3.5 text-[0.72rem] font-medium uppercase tracking-[0.18em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft disabled:opacity-50 sm:w-auto"
        >
          {submitting ? "Sending…" : "Send request"}
        </button>
        <p className="text-xs text-zaro-stone">
          We reply to every request. Your details stay within the studio.
        </p>
      </div>
    </form>
  );
}