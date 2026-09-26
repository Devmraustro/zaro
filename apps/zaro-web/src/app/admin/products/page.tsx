"use client";

/**
 * Staff product management list.
 *
 * Backed by GET /admin/products?page&page_size&status&search (products.read)
 * plus the existing per-row actions. The API caps page_size at 100 and returns
 * has_next / has_previous, so pagination follows server truth rather than
 * guessing from the item count.
 *
 * Row actions intentionally surface the API's own error text: a read-only role
 * that attempts a write gets a clean 403 message rather than a silent no-op.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatPrice } from "@/lib/format";
import { mediaUrl } from "@/lib/media";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import {
  FeaturedBadge,
  FormError,
  StatusPill,
  StockLabel,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/admin/catalog/CatalogUi";
import type { AdminCategory, AdminProduct, AdminProductList, ProductStatus } from "@/types/api";

const PAGE_SIZE = 20;

const STATUS_FILTERS: Array<{ value: ProductStatus | ""; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Published" },
  { value: "archived", label: "Archived" },
];

export default function AdminProductsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ProductStatus | "">("");

  const [data, setData] = useState<AdminProductList | null>(null);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (status) params.set("status", status);
    if (search.trim()) params.set("search", search.trim());
    try {
      const result = await adminFetch<AdminProductList>(`/admin/products?${params.toString()}`);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load products");
    }
  }, [page, status, search]);

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
        // The category column degrades to "Uncategorised"; the list still works.
        if (!cancelled) setCategories([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const categoryName = (id: string | null) =>
    id === null ? "Uncategorised" : categories.find((c) => c.id === id)?.name ?? "Uncategorised";

  const runAction = async (product: AdminProduct, action: "publish" | "archive") => {
    setBusyId(product.id);
    setActionError(null);
    try {
      await adminFetch<AdminProduct>(`/admin/products/${product.id}/${action}`, { method: "POST" });
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : `Could not ${action} product`);
    } finally {
      setBusyId(null);
    }
  };

  const toggleFeatured = async (product: AdminProduct) => {
    setBusyId(product.id);
    setActionError(null);
    try {
      await adminFetch<AdminProduct>(`/admin/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_featured: !product.is_featured }),
      });
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not update featured flag");
    } finally {
      setBusyId(null);
    }
  };

  const onSearchSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    // Re-run the same query even when the text is unchanged.
    void load();
  };

  // Server truth wins: it echoes the page it actually served, so the range can
  // never drift from the rows on screen.
  const currentPage = data?.page ?? page;
  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const to = Math.min(currentPage * PAGE_SIZE, total);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-medium text-zaro-black">Products</h1>
          <p className="mt-1 text-sm text-zaro-steel">
            Every record, including drafts and archived pieces.
          </p>
        </div>
        <Link href="/admin/products/new" className={primaryButtonClass}>
          New product
        </Link>
      </div>

      <form
        onSubmit={onSearchSubmit}
        className="mt-6 flex flex-wrap items-end gap-3 border border-zaro-graphite/10 bg-zaro-paper p-4 shadow-lift"
      >
        <label className="flex min-w-56 flex-1 flex-col gap-1.5">
          <span className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Search by name</span>
          <input
            type="search"
            value={search}
            maxLength={200}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Table, chair, cabinet…"
            aria-label="Search products by name"
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Status</span>
          <select
            value={status}
            aria-label="Filter by status"
            onChange={(e) => {
              setStatus(e.target.value as ProductStatus | "");
              setPage(1);
            }}
            className={inputClass}
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className={secondaryButtonClass}>
          Search
        </button>
      </form>

      {actionError ? (
        <div className="mt-4">
          <FormError message={actionError} />
        </div>
      ) : null}

      {error && !data && (
        <div className="mt-6">
          <ErrorState message={error} onRetry={() => void load()} />
        </div>
      )}
      {!data && !error && (
        <div className="mt-6">
          <LoadingState label="Loading products" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="mt-8">
          <EmptyState
            title={search.trim() || status ? "No matching products" : "No products yet"}
            description={
              search.trim() || status
                ? "Try a different search term or clear the status filter."
                : "Create the first product to start building the catalog."
          }
          action={
            search.trim() || status ? (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setStatus("");
                  setPage(1);
                }}
                className={`mt-6 ${secondaryButtonClass}`}
              >
                Clear filters
              </button>
            ) : (
              <Link href="/admin/products/new" className={`mt-6 ${primaryButtonClass}`}>
                New product
              </Link>
            )
          }
        />
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="mt-6 overflow-x-auto border border-zaro-graphite/10 bg-zaro-paper shadow-lift">
            <table className="w-full min-w-[60rem] text-sm">
              <thead>
                <tr className="border-b border-zaro-graphite/10 text-[0.625rem] uppercase tracking-[0.18em] text-zaro-stone">
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Image</th>
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Product</th>
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Category</th>
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Price</th>
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Stock</th>
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Status</th>
                  <th scope="col" className="px-4 py-3.5 text-start font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <ProductRow
                    key={p.id}
                    product={p}
                    categoryName={categoryName(p.category_id)}
                    busy={busyId === p.id}
                    onPublish={() => void runAction(p, "publish")}
                    onArchive={() => void runAction(p, "archive")}
                    onToggleFeatured={() => void toggleFeatured(p)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-zaro-steel">{`Showing ${from}–${to} of ${total}`}</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={!data.has_previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className={secondaryButtonClass}
              >
                Previous
              </button>
              <span className="text-xs text-zaro-steel">Page {data.page}</span>
              <button
                type="button"
                disabled={!data.has_next}
                onClick={() => setPage((p) => p + 1)}
                className={secondaryButtonClass}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ProductRow({
  product,
  categoryName,
  busy,
  onPublish,
  onArchive,
  onToggleFeatured,
}: {
  product: AdminProduct;
  categoryName: string;
  busy: boolean;
  onPublish: () => void;
  onArchive: () => void;
  onToggleFeatured: () => void;
}) {
  const [showActions, setShowActions] = useState(false);
  const hero = product.media.find((m) => m.media_kind === "hero") ?? product.media[0];

  return (
    <tr className="border-b border-zaro-graphite/5 align-middle last:border-b-0">
      <td className="px-4 py-3">
        <span className="block size-12 overflow-hidden rounded-sm bg-zaro-ivory">
          {hero ? (
            /* eslint-disable-next-line @next/next/no-img-element -- admin tooling, image URLs come from the API */
            <img
              src={mediaUrl(`/api/v1/files/${hero.id}/public-content`)}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : null}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <Link
          href={`/admin/products/${product.id}`}
          className="font-medium text-zaro-graphite underline-offset-4 hover:underline"
        >
          {product.name}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[0.65rem] text-zaro-stone">{product.product_code}</span>
          <FeaturedBadge featured={product.is_featured} />
          <span className="text-[0.65rem] text-zaro-stone">
            {product.media.length} image{product.media.length === 1 ? "" : "s"}
          </span>
        </div>
      </td>
      <td className="px-4 py-3.5 text-zaro-steel">{categoryName}</td>
      <td className="px-4 py-3.5">
        {product.selling_price_minor > 0 ? (
          formatPrice(product.selling_price_minor, product.currency)
        ) : (
          <span className="text-xs uppercase tracking-[0.14em] text-amber-700">Not set</span>
        )}
      </td>
      <td className="px-4 py-3.5">
        <StockLabel status={product.stock_status} />
      </td>
      <td className="px-4 py-3.5">
        <StatusPill status={product.status} />
      </td>
      <td className="px-4 py-3.5">
        <div className="flex flex-wrap items-center gap-3">
          <Link href={`/admin/products/${product.id}`} className="text-[0.62rem] uppercase tracking-[0.14em] text-zaro-bronze-dark hover:text-zaro-graphite">
            Open
          </Link>
          <button
            type="button"
            disabled={busy}
            onClick={onToggleFeatured}
            className="text-[0.62rem] uppercase tracking-[0.14em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite disabled:opacity-40"
          >
            {product.is_featured ? "Unfeature" : "Feature"}
          </button>
          {product.status === "draft" ? (
            <button
              type="button"
              disabled={busy}
              onClick={onPublish}
              className="text-[0.62rem] uppercase tracking-[0.14em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite disabled:opacity-40"
            >
              Publish
            </button>
          ) : null}
          {product.status === "active" ? (
            <button
              type="button"
              disabled={busy}
              onClick={showActions ? onArchive : () => setShowActions(true)}
              className="text-[0.62rem] uppercase tracking-[0.14em] text-red-700 transition-colors hover:text-red-900 disabled:opacity-40"
            >
              {showActions ? "Confirm archive" : "Archive"}
            </button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}
