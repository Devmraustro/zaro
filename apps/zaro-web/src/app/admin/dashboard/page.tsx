"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { adminFetch, hasActiveSession } from "@/lib/admin-auth";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import type { DashboardSummary } from "@/types/api";

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  needs_information: "Needs information",
  quotation_pending: "Quotation pending",
  converted: "Converted",
  cancelled: "Cancelled",
};

interface Kpi {
  label: string;
  value: number;
  sub?: string;
}

export default function AdminDashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await adminFetch<DashboardSummary>("/admin/dashboard");
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    hasActiveSession().then((active) => {
      if (!cancelled && !active) {
        router.replace("/admin");
        return;
      }
      void load();
    });
    return () => {
      cancelled = true;
    };
  }, [load, router]);

  const kpis: Kpi[] = [];
  if (summary?.custom_requests) {
    kpis.push({
      label: "Custom requests",
      value: summary.custom_requests.total,
      sub: `${summary.custom_requests.pending} pending`,
    });
    kpis.push({ label: "New this week", value: summary.custom_requests.this_week });
  }
  if (summary?.customers_total !== undefined) {
    kpis.push({ label: "Customers", value: summary.customers_total });
  }
  if (summary?.products) {
    kpis.push({
      label: "Products",
      value: summary.products.total,
      sub: `${summary.products.active} live`,
    });
  }

  return (
    <div>
      <div>
        <h1 className="font-serif text-2xl font-medium text-zaro-black">Dashboard</h1>
        <p className="mt-1 text-sm text-zaro-steel">A live overview of requests, customers, and catalog.</p>
      </div>

      {error && !summary && (
        <div className="mt-6">
          <ErrorState message={error} />
        </div>
      )}
      {!summary && !error && (
        <div className="mt-6">
          <LoadingState label="Loading overview" />
        </div>
      )}

      {summary && (
        <>
          <dl className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
            {kpis.map((kpi) => (
              <div key={kpi.label} className="border border-zaro-graphite/10 bg-zaro-paper p-5 shadow-lift">
                <dt className="text-[0.65rem] font-medium uppercase tracking-[0.16em] text-zaro-stone">{kpi.label}</dt>
                <dd className="mt-2 font-serif text-3xl font-medium text-zaro-black">{kpi.value}</dd>
                {kpi.sub ? <dd className="mt-1 text-xs text-zaro-steel">{kpi.sub}</dd> : null}
              </div>
            ))}
          </dl>

          {summary.recent_requests && (
            <section className="mt-10" aria-labelledby="recent-heading">
              <h2 id="recent-heading" className="font-serif text-lg font-medium text-zaro-black">
                Recent requests
              </h2>
              {summary.recent_requests.length === 0 ? (
                <div className="mt-4">
                  <EmptyState
                    title="No requests yet"
                    description="Requests submitted through the custom-order form will appear here."
                  />
                </div>
              ) : (
                <ul className="mt-4 space-y-3">
                  {summary.recent_requests.map((r) => (
                    <li
                      key={r.id}
                      className="flex flex-wrap items-center justify-between gap-3 border border-zaro-graphite/10 bg-zaro-paper px-5 py-3.5 shadow-lift"
                    >
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                        <span className="font-mono text-xs font-semibold text-zaro-bronze-dark">{r.reference}</span>
                        <span className="font-medium text-zaro-graphite capitalize">{r.product_type}</span>
                        <span className="text-sm text-zaro-stone">{r.customer_name}</span>
                        {r.wilaya ? <span className="text-xs text-zaro-stone/70">{r.wilaya}</span> : null}
                      </div>
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="rounded-full bg-zaro-ivory px-2.5 py-0.5 text-[0.625rem] uppercase tracking-[0.14em] text-zaro-stone">
                          {STATUS_LABELS[r.status] ?? r.status}
                        </span>
                        {r.created_at ? (
                          <span className="font-mono text-[0.6rem] uppercase text-zaro-stone/70">
                            {new Date(r.created_at).toLocaleDateString()}
                          </span>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}