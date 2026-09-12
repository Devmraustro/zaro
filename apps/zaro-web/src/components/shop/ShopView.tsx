"use client";

import { useCallback, useEffect, useState } from "react";
import CategoryCard from "@/components/CategoryCard";
import ProductGrid from "@/components/ProductGrid";
import { apiFetch } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import { ArrowLeft, ArrowRight, ChevronDown, Search } from "@/components/ui/icons";
import type { Category, PaginatedProducts } from "@/types/api";

const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "name", label: "Name A–Z" },
  { value: "price_asc", label: "Price, low to high" },
  { value: "price_desc", label: "Price, high to low" },
] as const;

const selectClass =
  "appearance-none border-b border-zaro-graphite/15 bg-transparent py-2 pe-9 ps-0.5 text-sm text-zaro-graphite outline-none transition-colors hover:border-zaro-graphite/40 focus:border-zaro-bronze cursor-pointer";

const inputClass =
  "w-full border-b border-zaro-graphite/15 bg-transparent py-2 ps-10 text-sm text-zaro-graphite outline-none transition-colors placeholder:text-zaro-stone focus:border-zaro-bronze";

export default function ShopView({
  initialCategories,
  initialData,
  initialError,
  requestedCategory,
  requestedSort,
  requestedPage,
  requestedSearch,
}: {
  initialCategories: Category[];
  initialData: PaginatedProducts | null;
  initialError: string | null;
  requestedCategory: string;
  requestedSort: string;
  requestedPage: number;
  requestedSearch: string;
}) {
  const [categories, setCategories] = useState<Category[]>(initialCategories);
  const [data, setData] = useState<PaginatedProducts | null>(initialData);
  const [error, setError] = useState<string | null>(initialError);
  const [loading, setLoading] = useState(initialData === null);

  const [category, setCategory] = useState(requestedCategory);
  const [sort, setSort] = useState(requestedSort);
  const [page, setPage] = useState(requestedPage);
  const [search, setSearch] = useState(requestedSearch);

  useEffect(() => {
    apiFetch<Category[]>("/categories")
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  const load = useCallback(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams({ page: String(page), sort });
      if (category) params.set("category", category);
      if (search.trim()) params.set("search", search.trim());
      apiFetch<PaginatedProducts>(`/products?${params.toString()}`)
        .then((result) => {
          if (!cancelled) setData(result);
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, search.trim() ? 260 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [category, search, sort, page]);

  useEffect(() => load(), [load]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const showLoading = loading && !data;
  const showError = error && !data;

  return (
    <div className="mx-auto max-w-[100rem] px-6 sm:px-10 lg:px-16">
      {/* Categories */}
      {categories.length > 0 && (
        <div className="grid grid-cols-1 gap-x-6 gap-y-12 pb-20 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((c) => (
            <CategoryCard key={c.id} category={c} />
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-x-8 gap-y-6 border-t border-zaro-graphite/10 pt-8">
        <label className="relative min-w-0 flex-1 basis-72">
          <span className="sr-only">Search products</span>
          <span aria-hidden="true" className="absolute inset-y-0 start-0 flex items-center text-zaro-stone">
            <Search className="size-4" />
          </span>
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search the collection"
            aria-label="Search products"
            className={inputClass}
          />
        </label>

        <label className="relative">
          <span className="sr-only">Filter by category</span>
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by category"
            className={selectClass}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 end-0 flex items-center text-zaro-stone"
          >
            <ChevronDown className="size-4" />
          </span>
        </label>

        <label className="relative">
          <span className="sr-only">Sort products</span>
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(1);
            }}
            aria-label="Sort products"
            className={selectClass}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 end-0 flex items-center text-zaro-stone"
          >
            <ChevronDown className="size-4" />
          </span>
        </label>

        {data && data.total > 0 && (
          <p className="ms-auto pb-2 text-xs uppercase tracking-[0.18em] text-zaro-stone">
            {data.total} {data.total === 1 ? "piece" : "pieces"}
          </p>
        )}
      </div>

      {/* Results */}
      <div className="pt-14">
        {showError && <ErrorState message={initialError ?? "The catalog is temporarily unavailable."} />}

        {showLoading && <LoadingState label="Opening the collection" />}

        {data && data.items.length === 0 && (
          <EmptyState
            title="The collection is being prepared"
            description="New pieces are being crafted in the studio. Until they arrive, tell us what you need — most of our work begins as a conversation."
          />
        )}

        {data && data.items.length > 0 && (
          <>
            <ProductGrid products={data.items} />
            {totalPages > 1 && (
              <nav aria-label="Pagination" className="mt-16 flex items-center justify-center gap-6 text-sm">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-[0.7rem] uppercase tracking-[0.18em] text-zaro-graphite/70 transition-colors hover:text-zaro-bronze disabled:opacity-40 disabled:hover:text-zaro-graphite/70"
                >
                  <ArrowLeft className="size-4" />
                  Previous
                </button>
                <span className="font-mono text-xs text-zaro-stone">
                  {data.page} / {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-[0.7rem] uppercase tracking-[0.18em] text-zaro-graphite/70 transition-colors hover:text-zaro-bronze disabled:opacity-40 disabled:hover:text-zaro-graphite/70"
                >
                  Next
                  <ArrowRight className="size-4" />
                </button>
              </nav>
            )}
          </>
        )}
      </div>
    </div>
  );
}