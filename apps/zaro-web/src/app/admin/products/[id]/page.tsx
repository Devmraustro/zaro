"use client";

/**
 * Central product workspace: everything staff can do to one product, in order
 * of the workflow — details, price, images, variants, publishing.
 *
 * Endpoint map (all pre-existing; no new backend surface):
 *   GET    /admin/products/{id}                    products.read
 *   PATCH  /admin/products/{id}                    products.update
 *   POST   /admin/products/{id}/price              products.manage_price
 *   POST   /admin/products/{id}/publish            products.update
 *   POST   /admin/products/{id}/archive            products.update
 *   GET    /admin/categories                       products.read
 *   media + variants                              see ProductMediaManager
 *
 * Fields the API does not return (weight_kg, meta_title, meta_description) are
 * deliberately absent from this form: an unreadable field cannot be edited
 * safely, and writing one blind risks clobbering stored values.
 */

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatPrice } from "@/lib/format";
import { ErrorState, LoadingState } from "@/components/ui/StateViews";
import ProductMediaManager from "@/components/admin/catalog/ProductMediaManager";
import {
  FeaturedBadge,
  Field,
  FormError,
  SectionCard,
  StatusPill,
  StockLabel,
  inputClass,
  primaryButtonClass,
  quietButtonClass,
  secondaryButtonClass,
} from "@/components/admin/catalog/CatalogUi";
import type {
  AdminCategory,
  AdminProduct,
  DimensionsInput,
  MaterialSpecInput,
  ProductUpdateInput,
  StockStatus,
} from "@/types/api";

const STOCK_OPTIONS: Array<{ value: StockStatus; label: string }> = [
  { value: "made_to_order", label: "Made to order" },
  { value: "in_stock", label: "In stock" },
  { value: "out_of_stock", label: "Out of stock" },
];

const UNITS: DimensionsInput["unit"][] = ["cm", "mm", "m", "in"];

interface DetailsDraft {
  name: string;
  description: string;
  category_id: string;
  stock_status: StockStatus;
  production_time_days: string;
  delivery_available: boolean;
  delivery_info: string;
  is_featured: boolean;
  dimensions: DimensionsInput | null;
  materials: MaterialSpecInput[];
}

function draftFromProduct(product: AdminProduct): DetailsDraft {
  const dims = product.dimensions as Partial<DimensionsInput> | null;
  const width = typeof dims?.width === "number" ? dims.width : null;
  return {
    name: product.name,
    description: product.description ?? "",
    category_id: product.category_id ?? "",
    stock_status: (product.stock_status as StockStatus) ?? "made_to_order",
    production_time_days:
      product.production_time_days === null ? "" : String(product.production_time_days),
    delivery_available: product.delivery_available,
    delivery_info: product.delivery_info ?? "",
    is_featured: product.is_featured,
    dimensions:
      width === null
        ? null
        : {
            width,
            height: typeof dims?.height === "number" ? dims.height : null,
            depth: typeof dims?.depth === "number" ? dims.depth : null,
            unit: (dims?.unit as DimensionsInput["unit"]) ?? "cm",
          },
    materials: (product.materials_spec ?? []).map((m) => ({
      name: String(m.name ?? ""),
      grade: typeof m.grade === "string" ? m.grade : null,
      finish: typeof m.finish === "string" ? m.finish : null,
    })),
  };
}

export default function AdminProductWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [product, setProduct] = useState<AdminProduct | null>(null);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [draft, setDraft] = useState<DetailsDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sectionError, setSectionError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const justCreated = searchParams.get("created") === "1";
  const priceError = searchParams.get("price_error");

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await adminFetch<AdminProduct>(`/admin/products/${id}`);
      setProduct(data);
      setDraft(draftFromProduct(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load product");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    adminFetch<AdminCategory[]>("/admin/categories")
      .then((rows) => {
        if (!cancelled) setCategories(rows);
      })
      .catch(() => {
        if (!cancelled) setCategories([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const saveDetails = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setSectionError(null);
    setSaved(false);
    try {
      const payload: ProductUpdateInput = {
        name: draft.name.trim(),
        category_id: draft.category_id === "" ? null : draft.category_id,
        stock_status: draft.stock_status,
        delivery_available: draft.delivery_available,
        is_featured: draft.is_featured,
        // Empty string clears a nullable text field: the API treats a null as
        // "leave unchanged", so an empty box would otherwise be ignored.
        description: draft.description.trim(),
        delivery_info: draft.delivery_info.trim(),
        materials_spec: draft.materials.length > 0 ? draft.materials : null,
        dimensions: draft.dimensions,
        // Always sent: the API treats an absent key as "leave unchanged" but an
        // explicit null as "clear". Omitting it here would silently keep the
        // stored value after the admin empties the box.
        production_time_days: draft.production_time_days.trim()
          ? Number(draft.production_time_days)
          : null,
      };
      const updated = await adminFetch<AdminProduct>(`/admin/products/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setProduct(updated);
      setDraft(draftFromProduct(updated));
      setSaved(true);
    } catch (err) {
      setSectionError(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setBusy(false);
    }
  };

  const runStatusAction = async (action: "publish" | "archive") => {
    setBusy(true);
    setSectionError(null);
    try {
      const updated = await adminFetch<AdminProduct>(`/admin/products/${id}/${action}`, {
        method: "POST",
      });
      setProduct(updated);
      setDraft(draftFromProduct(updated));
    } catch (err) {
      setSectionError(err instanceof Error ? err.message : `Could not ${action} product`);
    } finally {
      setBusy(false);
    }
  };

  if (error && !product) {
    return (
      <div>
        <BackLink />
        <div className="mt-6">
          <ErrorState message={error} onRetry={() => void load()} />
        </div>
      </div>
    );
  }

  if (!product || !draft) {
    return (
      <div>
        <BackLink />
        <div className="mt-6">
          <LoadingState label="Loading product" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <BackLink />

      <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-serif text-2xl font-medium text-zaro-black">{product.name}</h1>
            <StatusPill status={product.status} />
            <FeaturedBadge featured={product.is_featured} />
          </div>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zaro-steel">
            <span className="font-mono text-xs text-zaro-stone">{product.product_code}</span>
            <span>/{product.slug}</span>
            <StockLabel status={product.stock_status} />
            {product.status === "active" ? (
              <a href={`/products/${product.slug}`} className="text-zaro-bronze-dark underline-offset-4 hover:underline">
                View public page →
              </a>
            ) : null}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {product.status === "draft" ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void runStatusAction("publish")}
              className={primaryButtonClass}
            >
              {busy ? "Working…" : "Publish"}
            </button>
          ) : null}
          {product.status === "active" ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void runStatusAction("archive")}
              className={secondaryButtonClass}
            >
              Archive
            </button>
          ) : null}
          {product.status === "archived" ? (
            <p className="text-xs leading-relaxed text-zaro-steel">
              Archived products stay read-only in the catalog.
            </p>
          ) : null}
        </div>
      </div>

      {justCreated ? (
        <p data-testid="created-notice" className="mt-4 rounded-sm border border-[#cfdfc9] bg-[#eef4ea] px-4 py-3 text-sm text-[#3e5f3f]">
          Product created as a draft. Add images, then publish when the price is set.
        </p>
      ) : null}
      {priceError ? (
        <div className="mt-4">
          <FormError message={`The product was created, but the price was not saved: ${priceError}`} />
        </div>
      ) : null}

      <div className="mt-6">
        <FormError message={sectionError} />
      </div>

      <div className="mt-6 flex flex-col gap-6">
        <form onSubmit={saveDetails}>
          <SectionCard
            title="Details"
            description="Name, description, category, measurements, materials and availability."
            action={
              <button type="submit" disabled={busy || draft.name.trim() === ""} className={primaryButtonClass}>
                {busy ? "Saving…" : "Save details"}
              </button>
            }
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Name" htmlFor="w-name">
                <input
                  id="w-name"
                  required
                  maxLength={200}
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Category" htmlFor="w-category" hint="Leave empty to uncategorise.">
                <select
                  id="w-category"
                  value={draft.category_id}
                  onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}
                  className={inputClass}
                >
                  <option value="">Uncategorised</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                      {c.is_active ? "" : " (inactive)"}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="mt-4">
              <Field label="Description" htmlFor="w-description">
                <textarea
                  id="w-description"
                  rows={5}
                  maxLength={20000}
                  value={draft.description}
                  onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>

            <fieldset className="mt-6">
              <legend className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Dimensions</legend>
              <div className="mt-3 grid gap-4 md:grid-cols-4">
                <Field label="Width" htmlFor="w-width">
                  <input
                    id="w-width"
                    type="number"
                    step="any"
                    min={0}
                    value={draft.dimensions?.width ?? ""}
                    onChange={(e) => {
                      const width = e.target.value;
                      setDraft({
                        ...draft,
                        dimensions:
                          width === ""
                            ? null
                            : { ...(draft.dimensions ?? { unit: "cm" }), width: Number(width) },
                      });
                    }}
                    className={inputClass}
                  />
                </Field>
                <Field label="Height" htmlFor="w-height">
                  <input
                    id="w-height"
                    type="number"
                    step="any"
                    min={0}
                    value={draft.dimensions?.height ?? ""}
                    onChange={(e) => {
                      const height = e.target.value;
                      setDraft({
                        ...draft,
                        dimensions: {
                          ...(draft.dimensions ?? { width: 0, unit: "cm" as const }),
                          height: height === "" ? null : Number(height),
                        },
                      });
                    }}
                    className={inputClass}
                  />
                </Field>
                <Field label="Depth" htmlFor="w-depth">
                  <input
                    id="w-depth"
                    type="number"
                    step="any"
                    min={0}
                    value={draft.dimensions?.depth ?? ""}
                    onChange={(e) => {
                      const depth = e.target.value;
                      setDraft({
                        ...draft,
                        dimensions: {
                          ...(draft.dimensions ?? { width: 0, unit: "cm" as const }),
                          depth: depth === "" ? null : Number(depth),
                        },
                      });
                    }}
                    className={inputClass}
                  />
                </Field>
                <Field label="Unit" htmlFor="w-unit">
                  <select
                    id="w-unit"
                    value={draft.dimensions?.unit ?? "cm"}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        dimensions: {
                          ...(draft.dimensions ?? { width: 0, unit: "cm" as const }),
                          unit: e.target.value as DimensionsInput["unit"],
                        },
                      })
                    }
                    className={inputClass}
                  >
                    {UNITS.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
            </fieldset>

            <fieldset className="mt-6">
              <legend className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Materials</legend>
              <div className="mt-3 flex flex-col gap-2">
                {draft.materials.map((material, index) => (
                  <div key={index} className="flex flex-wrap items-center gap-2">
                    <input
                      aria-label={`Material ${index + 1} name`}
                      maxLength={120}
                      value={material.name}
                      placeholder="Name"
                      onChange={(e) => {
                        const next = [...draft.materials];
                        next[index] = { ...material, name: e.target.value };
                        setDraft({ ...draft, materials: next });
                      }}
                      className={`w-44 ${inputClass}`}
                    />
                    <input
                      aria-label={`Material ${index + 1} grade`}
                      maxLength={60}
                      value={material.grade ?? ""}
                      placeholder="Grade"
                      onChange={(e) => {
                        const next = [...draft.materials];
                        next[index] = { ...material, grade: e.target.value || null };
                        setDraft({ ...draft, materials: next });
                      }}
                      className={`w-32 ${inputClass}`}
                    />
                    <input
                      aria-label={`Material ${index + 1} finish`}
                      maxLength={60}
                      value={material.finish ?? ""}
                      placeholder="Finish"
                      onChange={(e) => {
                        const next = [...draft.materials];
                        next[index] = { ...material, finish: e.target.value || null };
                        setDraft({ ...draft, materials: next });
                      }}
                      className={`w-32 ${inputClass}`}
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setDraft({ ...draft, materials: draft.materials.filter((_, i) => i !== index) })
                      }
                      className={quietButtonClass}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setDraft({ ...draft, materials: [...draft.materials, { name: "" }] })}
                  className={`self-start ${secondaryButtonClass}`}
                >
                  Add material
                </button>
              </div>
            </fieldset>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <Field label="Stock status" htmlFor="w-stock">
                <select
                  id="w-stock"
                  value={draft.stock_status}
                  onChange={(e) => setDraft({ ...draft, stock_status: e.target.value as StockStatus })}
                  className={inputClass}
                >
                  {STOCK_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Production time (days)" htmlFor="w-production">
                <input
                  id="w-production"
                  type="number"
                  min={0}
                  max={3650}
                  value={draft.production_time_days}
                  onChange={(e) => setDraft({ ...draft, production_time_days: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Delivery info" htmlFor="w-delivery">
                <input
                  id="w-delivery"
                  maxLength={2000}
                  value={draft.delivery_info}
                  onChange={(e) => setDraft({ ...draft, delivery_info: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>

            <div className="mt-5 flex flex-col gap-3">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.delivery_available}
                  onChange={(e) => setDraft({ ...draft, delivery_available: e.target.checked })}
                  className="size-4 accent-zaro-black"
                />
                <span className="text-sm text-zaro-graphite">Delivery available</span>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={draft.is_featured}
                  onChange={(e) => setDraft({ ...draft, is_featured: e.target.checked })}
                  className="mt-1 size-4 accent-zaro-black"
                />
                <span className="text-sm text-zaro-graphite">
                  Featured
                  <span className="block text-[0.65rem] leading-relaxed text-zaro-stone/80">
                    Eligible for the public featured filter. Must still be published to appear publicly.
                  </span>
                </span>
              </label>
            </div>

            {saved ? (
              <p data-testid="details-saved" className="mt-4 text-sm text-[#3e5f3f]">
                Changes saved.
              </p>
            ) : null}
          </SectionCard>
        </form>

        <PriceSection product={product} onSaved={load} />

        <SectionCard
          title="Images"
          description="The first hero image leads the public product page."
        >
          <ProductMediaManager productId={product.id} onError={setSectionError} />
        </SectionCard>

        <VariantsSection product={product} onChanged={load} />

        <p className="text-[0.65rem] leading-relaxed text-zaro-stone/80">
          Need to rename the product or move it to another category? Use{" "}
          <button type="button" onClick={() => router.push("/admin/products")} className={quietButtonClass}>
            back to products
          </button>{" "}
          to leave this view.
        </p>
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/admin/products"
      className="text-[0.65rem] uppercase tracking-[0.2em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite"
    >
      ← Back to products
    </Link>
  );
}

function PriceSection({ product, onSaved }: { product: AdminProduct; onSaved: () => Promise<void> }) {
  const [major, setMajor] = useState(
    product.selling_price_minor > 0 ? String(product.selling_price_minor / 100) : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = Number(major.trim());
    if (!Number.isFinite(value) || value < 0) {
      setError("Enter the price as a number, for example 149000.");
      return;
    }
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await adminFetch<AdminProduct>(`/admin/products/${product.id}/price`, {
        method: "POST",
        body: JSON.stringify({ selling_price_minor: Math.round(value * 100) }),
      });
      setDone(true);
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set price");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard
      title="Price"
      description="Price changes are audited with their previous value and need price-management permission."
    >
      <form onSubmit={submit} className="flex flex-wrap items-end gap-4">
        <Field
          label="Selling price"
          htmlFor="w-price"
          hint={
            major.trim() === ""
              ? "Not set — publishing is blocked until a positive price exists."
              : `Stored as ${formatPrice(Math.round(Number(major) * 100), product.currency)}.`
          }
        >
          <input
            id="w-price"
            type="text"
            inputMode="decimal"
            value={major}
            onChange={(e) => setMajor(e.target.value)}
            placeholder="149000"
            className={inputClass}
          />
        </Field>
        <button type="submit" disabled={busy} className={secondaryButtonClass}>
          {busy ? "Saving…" : "Update price"}
        </button>
        {done ? (
          <span data-testid="price-saved" className="text-sm text-[#3e5f3f]">
            Price updated.
          </span>
        ) : null}
      </form>
      <div className="mt-4">
        <FormError message={error} />
      </div>
    </SectionCard>
  );
}

function VariantsSection({ product, onChanged }: { product: AdminProduct; onChanged: () => Promise<void> }) {
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const active = useMemo(
    () => product.variants.filter((v) => v.is_active).length,
    [product.variants],
  );

  const addVariant = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (label.trim() === "") return;
    setBusy(true);
    setError(null);
    try {
      await adminFetch(`/admin/products/${product.id}/variants`, {
        method: "POST",
        body: JSON.stringify({ label: label.trim() }),
      });
      setLabel("");
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add variant");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard
      title="Variants"
      description="Sizes and finishes. The SKU is generated from the product code."
    >
      {product.variants.length === 0 ? (
        <p className="text-sm text-zaro-steel">
          No variants — this product uses a single price.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {product.variants.map((variant) => (
            <li
              key={variant.id}
              className="flex flex-wrap items-center justify-between gap-3 border border-zaro-graphite/10 bg-zaro-ivory/40 px-4 py-2.5"
            >
              <span className="text-sm text-zaro-graphite">{variant.label}</span>
              <span className="font-mono text-[0.65rem] text-zaro-stone">{variant.sku}</span>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={addVariant} className="mt-5 flex flex-wrap items-end gap-3">
        <Field label="New variant" htmlFor="w-variant">
          <input
            id="w-variant"
            maxLength={200}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="180cm / natural oak"
            className={`w-56 ${inputClass}`}
          />
        </Field>
        <button type="submit" disabled={busy || label.trim() === ""} className={secondaryButtonClass}>
          {busy ? "Adding…" : "Add variant"}
        </button>
        {active > 0 ? (
          <p className="pb-2 text-xs text-zaro-stone">
            {active} active of {product.variants.length}
          </p>
        ) : null}
      </form>
      <div className="mt-4">
        <FormError message={error} />
      </div>
    </SectionCard>
  );
}
