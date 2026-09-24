"use client";

import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";

interface AdminCustomer {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  city: string | null;
  municipality: string | null;
  wilaya: string | null;
  status: string;
  created_at: string;
}

const inputClass =
  "w-full border-b border-zaro-graphite/15 bg-transparent px-0.5 py-2 text-sm text-zaro-graphite outline-none transition-colors placeholder:text-zaro-stone focus:border-zaro-bronze";

export default function AdminCustomersPage() {
  const [customers, setCustomers] = useState<AdminCustomer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [wilaya, setWilaya] = useState("");

  const load = useCallback(async () => {
    try {
      setError(null);
      const params = new URLSearchParams({ page_size: "100" });
      if (search.trim()) params.set("search", search.trim());
      if (wilaya.trim()) params.set("wilaya", wilaya.trim());
      const data = await adminFetch<{ items: AdminCustomer[] }>(
        `/admin/customers?${params.toString()}`,
      );
      setCustomers(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, [search, wilaya]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div>
        <h1 className="font-serif text-2xl font-medium text-zaro-black">Customers</h1>
        <p className="mt-1 text-sm text-zaro-steel">Customer records and their delivery region.</p>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 sm:max-w-2xl sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-[0.62rem] font-medium uppercase tracking-[0.16em] text-zaro-stone">
            Search
          </span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, email, phone…"
            aria-label="Search customers"
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[0.62rem] font-medium uppercase tracking-[0.16em] text-zaro-stone">
            Wilaya
          </span>
          <input
            type="text"
            value={wilaya}
            onChange={(e) => setWilaya(e.target.value)}
            placeholder="e.g. 16 — Algiers"
            aria-label="Filter by wilaya"
            className={inputClass}
          />
        </label>
      </div>

      {error && !customers && <div className="mt-6"><ErrorState message={error} /></div>}
      {!customers && !error && <div className="mt-6"><LoadingState label="Loading customers" /></div>}

      {customers && customers.length === 0 && (
        <div className="mt-6">
          <EmptyState title="No customers" description="No customers match this view." />
        </div>
      )}

      {customers && customers.length > 0 && (
        <div className="mt-8 overflow-x-auto">
          <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-zaro-graphite/15 text-[0.62rem] uppercase tracking-[0.16em] text-zaro-stone">
                <th className="py-2.5 pr-4 font-medium">Name</th>
                <th className="py-2.5 pr-4 font-medium">Contact</th>
                <th className="py-2.5 pr-4 font-medium">Location</th>
                <th className="py-2.5 pr-4 font-medium">Status</th>
                <th className="py-2.5 pr-4 font-medium">Added</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id} className="border-b border-zaro-graphite/8">
                  <td className="py-3 pr-4 font-medium text-zaro-graphite">{c.full_name}</td>
                  <td className="py-3 pr-4 text-zaro-steel">
                    {c.email ?? "no email"}
                    {c.phone ? ` · ${c.phone}` : ""}
                  </td>
                  <td className="py-3 pr-4 text-zaro-steel">
                    {[c.wilaya, c.municipality, c.city].filter(Boolean).join(" · ") || "—"}
                  </td>
                  <td className="py-3 pr-4">
                    <span className="rounded-full bg-zaro-ivory px-2.5 py-0.5 text-[0.625rem] uppercase tracking-[0.14em] capitalize text-zaro-stone">
                      {c.status}
                    </span>
                  </td>
                  <td className="py-3 pr-4 font-mono text-[0.6rem] uppercase text-zaro-stone/70">
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}