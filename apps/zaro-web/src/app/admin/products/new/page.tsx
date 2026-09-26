"use client";

/**
 * New product form.
 *
 * Uses the existing two-step backend flow rather than inventing one:
 *   1. POST /admin/products  (products.create) — always creates a draft. The
 *      product code and slug are server-generated.
 *   2. POST /admin/products/{id}/price (products.manage_price) — required
 *      before the product can be published.
 *
 * A product with no price is legitimate (it stays a draft), so the price step
 * is offered inline and skippable rather than blocking creation.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatPrice } from "@/lib/format";
import {
  Field,
  FormError,
  SectionCard,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/admin/catalog/CatalogUi";
import type {
  AdminCategory,
  AdminProduct,
  DimensionsInput,
  ProductCreateInput,
  StockStatus,
} from "@/types/api";

const STOCK_OPTIONS: Array<{ value: StockStatus; label: string }> = [
  { value: "made_to_order", label: "Made to order" },
  { value: "in_stock", label: "In stock" },
  { value: "out_of_stock", label: "Out of stock" },
];

const UNITS: DimensionsInput["unit"][] = ["cm", "mm", "m", "in"];

/** Price is collected in whole currency units and sent as minor units. */
function toMinorUnits(major: string): number | null {
  const trimmed = major.trim();
  if (trimmed === "") return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < 0) return null;
  return Math.round(value * 100);
}

export default function NewProductPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<AdminCategory[]>([]);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [stockStatus, setStockStatus] = useState<StockStatus>("made_to_order");
  const [productionDays, setProductionDays] = useState("");
  const [deliveryAvailable, setDeliveryAvailable] = useState(true);
  const [deliveryInfo, setDeliveryInfo] = useState("");
  const [isFeatured, setIsFeatured] = useState(false);
  const [materials, setMaterials] = useState("");
  const [dimensions, setDimensions] = useState<DimensionsInput | null>(null);
  const [price, setPrice] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    adminFetch<AdminCategory[]>("/admin/categories")
      .then((rows) => {
        if (!cancelled) setCategories(rows.filter((c) => c.is_active));
      })
      .catch(() => {
        if (!cancelled) setCategories([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setBusy(true);
      setError(null);

      const priceMinor = toMinorUnits(price);
      if (price.trim() !== "" && priceMinor === null) {
        setError("Enter the price as a number, for example 149000.");
        setBusy(false);
        return;
      }

      const payload: ProductCreateInput = {
        name: name.trim(),
        category_id: categoryId === "" ? null : categoryId,
        stock_status: stockStatus,
        delivery_available: deliveryAvailable,
        is_featured: isFeatured,
      };
      if (description.trim()) payload.description = description.trim();
      if (deliveryInfo.trim()) payload.delivery_info = deliveryInfo.trim();
      if (productionDays.trim()) payload.production_time_days = Number(productionDays);
      if (materials.trim()) {
        payload.materials_spec = materials
          .split(",")
          .map((entry) => entry.trim())
          .filter((entry) => entry !== "")
          .map((entry) => ({ name: entry }));
      }
      if (dimensions) payload.dimensions = dimensions;

      try {
        const product = await adminFetch<AdminProduct>("/admin/products", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        if (priceMinor !== null) {
          try {
            await adminFetch<AdminProduct>(`/admin/products/${product.id}/price`, {
              method: "POST",
              body: JSON.stringify({ selling_price_minor: priceMinor }),
            });
          } catch (priceErr) {
            // The product exists; only the price failed (missing permission or
            // validation). Land on the workspace and explain, never on /new.
            router.push(
              `/admin/products/${product.id}?created=1&price_error=${encodeURIComponent(
                priceErr instanceof Error ? priceErr.message : "Price could not be set",
              )}`,
            );
            return;
          }
        }

        router.push(`/admin/products/${product.id}?created=1`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not create product");
        setBusy(false);
      }
    },
    [
      name,
      description,
      categoryId,
      stockStatus,
      productionDays,
      deliveryAvailable,
      deliveryInfo,
      isFeatured,
      materials,
      dimensions,
      price,
      router,
    ],
  );

  return (
    <div>
      <Link
        href="/admin/products"
        className="text-[0.65rem] uppercase tracking-[0.2em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite"
      >
        ← Back to products
      </Link>

      <h1 className="mt-5 font-serif text-2xl font-medium text-zaro-black">New product</h1>
      <p className="mt-1 text-sm text-zaro-steel">
        Created as a draft with a generated code. Add images and publish once the price is set.
      </p>

      <form onSubmit={submit} className="mt-8 flex flex-col gap-6">
        <SectionCard title="Basics" description="Name and category drive the product code and public URL.">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name" htmlFor="p-name">
              <input
                id="p-name"
                required
                maxLength={200}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Atlas dining table"
                className={inputClass}
              />
            </Field>
            <Field label="Category" htmlFor="p-category" hint="Optional — can be set later.">
              <select
                id="p-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className={inputClass}
              >
                <option value="">Uncategorised</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Description" htmlFor="p-description">
              <textarea
                id="p-description"
                rows={5}
                maxLength={20000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What makes this piece worth owning"
                className={inputClass}
              />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Dimensions & materials" description="All optional. Measurements are required if you add dimensions.">
          <div className="grid gap-4 md:grid-cols-4">
            <Field label="Width" htmlFor="p-width">
              <input
                id="p-width"
                type="number"
                step="any"
                min={0}
                value={dimensions?.width ?? ""}
                onChange={(e) => {
                  const width = e.target.value;
                  setDimensions(width === "" ? null : { ...(dimensions ?? { unit: "cm" as const }), width: Number(width) });
                }}
                className={inputClass}
              />
            </Field>
            <Field label="Height" htmlFor="p-height">
              <input
                id="p-height"
                type="number"
                step="any"
                min={0}
                value={dimensions?.height ?? ""}
                onChange={(e) => {
                  const height = e.target.value;
                  if (!dimensions) return;
                  setDimensions({ ...dimensions, height: height === "" ? null : Number(height) });
                }}
                className={inputClass}
              />
            </Field>
            <Field label="Depth" htmlFor="p-depth">
              <input
                id="p-depth"
                type="number"
                step="any"
                min={0}
                value={dimensions?.depth ?? ""}
                onChange={(e) => {
                  const depth = e.target.value;
                  if (!dimensions) return;
                  setDimensions({ ...dimensions, depth: depth === "" ? null : Number(depth) });
                }}
                className={inputClass}
              />
            </Field>
            <Field label="Unit" htmlFor="p-unit">
              <select
                id="p-unit"
                value={dimensions?.unit ?? "cm"}
                onChange={(e) => {
                  if (!dimensions) return;
                  setDimensions({ ...dimensions, unit: e.target.value as DimensionsInput["unit"] });
                }}
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
          <div className="mt-4">
            <Field
              label="Materials"
              htmlFor="p-materials"
              hint="Comma separated, for example: Oak, Linen, Brass"
            >
              <input
                id="p-materials"
                value={materials}
                onChange={(e) => setMaterials(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Price & availability">
          <div className="grid gap-4 md:grid-cols-3">
            <Field
              label="Selling price"
              htmlFor="p-price"
              hint={
                price.trim() === ""
                  ? "Optional now — required before publishing."
                  : `Will be stored as ${formatPrice(toMinorUnits(price) ?? 0)}.`
              }
            >
              <input
                id="p-price"
                type="text"
                inputMode="decimal"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="149000"
                className={inputClass}
              />
            </Field>
            <Field label="Stock status" htmlFor="p-stock">
              <select
                id="p-stock"
                value={stockStatus}
                onChange={(e) => setStockStatus(e.target.value as StockStatus)}
                className={inputClass}
              >
                {STOCK_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Production time (days)" htmlFor="p-production">
              <input
                id="p-production"
                type="number"
                min={0}
                max={3650}
                value={productionDays}
                onChange={(e) => setProductionDays(e.target.value)}
                placeholder="45"
                className={inputClass}
              />
            </Field>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Field label="Delivery info" htmlFor="p-delivery-info">
              <input
                id="p-delivery-info"
                maxLength={2000}
                value={deliveryInfo}
                onChange={(e) => setDeliveryInfo(e.target.value)}
                placeholder="Delivered in 2–4 weeks across Algeria"
                className={inputClass}
              />
            </Field>
            <label className="flex items-end gap-2 pb-2">
              <input
                id="p-delivery-available"
                type="checkbox"
                checked={deliveryAvailable}
                onChange={(e) => setDeliveryAvailable(e.target.checked)}
                className="size-4 accent-zaro-black"
              />
              <span className="text-sm text-zaro-graphite">Delivery available</span>
            </label>
          </div>
        </SectionCard>

        <SectionCard title="Merchandising">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={isFeatured}
              onChange={(e) => setIsFeatured(e.target.checked)}
              className="size-4 accent-zaro-black"
            />
            <span className="text-sm text-zaro-graphite">
              Feature this product
              <span className="block text-[0.65rem] leading-relaxed text-zaro-stone/80">
                Featured products are eligible for the public featured filter. A product must still be published to appear publicly.
              </span>
            </span>
          </label>
        </SectionCard>

        <FormError message={error} />

        <div className="flex items-center gap-3">
          <button type="submit" disabled={busy || name.trim() === ""} className={primaryButtonClass}>
            {busy ? "Creating…" : "Create draft"}
          </button>
          <Link href="/admin/products" className={secondaryButtonClass}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
