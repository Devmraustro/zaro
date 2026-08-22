"use client";

import { useEffect, useState } from "react";
import ProductCard from "@/components/ProductCard";
import { apiFetch } from "@/lib/api";
import type { Category, PaginatedProducts } from "@/types/api";

const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "name", label: "Name A–Z" },
  { value: "price_asc", label: "Price ↑" },
  { value: "price_desc", label: "Price ↓" },
];

export default function ShopPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [data, setData] = useState<PaginatedProducts | null>(null);
  const [category, setCategory] = useState<string>("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Category[]>("/catalog/categories")
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page: String(page), sort });
    if (category) params.set("category", category);
    if (search.trim()) params.set("search", search.trim());
    apiFetch<PaginatedProducts>(`/catalog/products?${params.toString()}`)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [category, search, sort, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <main className="mx-auto max-w-7xl px-6 py-16">
      <h1 className="font-serif text-3xl font-bold text-zaro-black">Shop</h1>
      <p className="mt-2 text-zaro-steel">Browse our collection of handcrafted furniture.</p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search products…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-64 border border-zaro-ivory-dark bg-white px-3 py-2 text-sm outline-none focus:border-zaro-bronze"
          aria-label="Search products"
        />
        <select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(1);
          }}
          className="border border-zaro-ivory-dark bg-white px-3 py-2 text-sm outline-none focus:border-zaro-bronze"
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => {
            setSort(e.target.value);
            setPage(1);
          }}
          className="border border-zaro-ivory-dark bg-white px-3 py-2 text-sm outline-none focus:border-zaro-bronze"
          aria-label="Sort products"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="mt-8 text-sm text-red-700">Failed to load products: {error}</div>}
      {loading && !data && <div className="mt-8 text-sm text-zaro-steel">Loading…</div>}

      {data && (
        <>
          {data.items.length === 0 ? (
            <div className="mt-8 text-sm text-zaro-steel">No products found.</div>
          ) : (
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {data.items.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}
          {totalPages > 1 && (
            <div className="mt-10 flex items-center justify-center gap-4 text-sm">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-4 py-2 border border-zaro-ivory-dark disabled:opacity-40 hover:border-zaro-bronze"
              >
                Previous
              </button>
              <span className="text-zaro-steel">
                Page {data.page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="px-4 py-2 border border-zaro-ivory-dark disabled:opacity-40 hover:border-zaro-bronze"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
