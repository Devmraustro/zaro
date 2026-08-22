"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { CustomRequestPublic, CustomRequestSubmit, ProductType } from "@/types/api";

const PRODUCT_TYPES: Array<{ value: ProductType; label: string }> = [
  { value: "table", label: "Table" },
  { value: "chair", label: "Chair" },
  { value: "sofa", label: "Sofa" },
  { value: "shelf", label: "Shelf / Storage" },
  { value: "bed", label: "Bed" },
  { value: "desk", label: "Desk" },
  { value: "metalwork", label: "Metalwork" },
  { value: "other", label: "Other" },
];

const inputClass =
  "w-full border border-zaro-ivory-dark bg-white px-3 py-2 text-sm outline-none focus:border-zaro-bronze";

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
      product_type: String(fd.get("product_type") ?? "other") as ProductType,
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
      <div className="border border-zaro-bronze/40 bg-white p-8 text-center" data-testid="request-success">
        <h2 className="font-serif text-2xl font-semibold text-zaro-black">Request received</h2>
        <p className="mt-3 text-sm text-zaro-steel">
          Your reference is{" "}
          <span className="font-mono font-semibold text-zaro-bronze">{result.reference}</span>. Our
          team will review it and get back to you shortly.
        </p>
        <button
          type="button"
          onClick={() => setResult(null)}
          className="mt-6 border border-zaro-bronze px-6 py-2 text-xs uppercase tracking-wider text-zaro-bronze transition-colors hover:bg-zaro-bronze hover:text-zaro-ivory"
        >
          Submit another request
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" data-testid="custom-request-form">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Full name *</span>
          <input name="full_name" required minLength={2} maxLength={200} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Product type *</span>
          <select name="product_type" required defaultValue="table" className={inputClass}>
            {PRODUCT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Email</span>
          <input name="email" type="email" className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Phone</span>
          <input name="phone" className={inputClass} />
        </label>
      </div>

      <label className="block">
        <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">
          Describe your project * <span className="normal-case">(min. 10 characters)</span>
        </span>
        <textarea name="description" required minLength={10} maxLength={4000} rows={5} className={inputClass} />
      </label>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Desired dimensions</span>
          <input name="desired_dimensions" placeholder="e.g. 200 × 90 × 75 cm" className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Materials</span>
          <input name="materials" placeholder="e.g. solid oak, blackened steel" className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Colors</span>
          <input name="colors" className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Finish</span>
          <input name="finish" className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Quantity</span>
          <input name="quantity" type="number" min={1} max={1000} defaultValue={1} className={inputClass} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Budget min (DA)</span>
            <input name="budget_min" inputMode="decimal" className={inputClass} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Budget max (DA)</span>
            <input name="budget_max" inputMode="decimal" className={inputClass} />
          </label>
        </div>
      </div>

      {error && (
        <div role="alert" className="text-sm text-red-700">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-zaro-black px-8 py-3 text-sm font-medium uppercase tracking-wider text-zaro-ivory transition-colors hover:bg-zaro-graphite disabled:opacity-50 sm:w-auto"
      >
        {submitting ? "Sending…" : "Send request"}
      </button>
    </form>
  );
}
