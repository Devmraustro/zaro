"use client";

import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatBudgetRange } from "@/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import { ArrowRight } from "@/components/ui/icons";
import type { AdminCustomRequest } from "@/types/api";

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  needs_information: "Needs information",
  quotation_pending: "Quotation pending",
  converted: "Converted",
  cancelled: "Cancelled",
};

const NEXT_STATUSES: Record<string, string[]> = {
  submitted: ["under_review", "cancelled"],
  under_review: ["needs_information", "quotation_pending", "cancelled"],
  needs_information: ["under_review", "cancelled"],
  quotation_pending: ["converted", "cancelled"],
  converted: [],
  cancelled: [],
};

export default function AdminCustomRequestsPage() {
  const [requests, setRequests] = useState<AdminCustomRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await adminFetch<{ items: AdminCustomRequest[] }>(
        "/admin/custom-requests?page_size=50",
      );
      setRequests(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function transition(id: string, status: string) {
    setBusyId(id);
    setActionError(null);
    try {
      await adminFetch(`/admin/custom-requests/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Transition failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div>
        <h1 className="font-serif text-2xl font-medium text-zaro-black">Custom Requests</h1>
        <p className="mt-1 text-sm text-zaro-steel">Inbound briefs from the bespoke form.</p>
      </div>

      {actionError && (
        <div role="alert" className="mt-6 border border-red-300/60 bg-red-50/50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </div>
      )}
      {error && !requests && <div className="mt-6"><ErrorState message={error} /></div>}
      {!requests && !error && <div className="mt-6"><LoadingState label="Loading requests" /></div>}

      {requests && requests.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="No requests yet"
            description="Requests submitted through the custom-order form will appear here."
          />
        </div>
      )}

      {requests && requests.length > 0 && (
        <div className="mt-8 space-y-4">
          {requests.map((r) => (
            <article
              key={r.id}
              className="border border-zaro-graphite/10 bg-zaro-paper p-5 shadow-lift"
              data-testid="custom-request-row"
            >
              <header className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-mono text-xs font-semibold text-zaro-bronze-dark">{r.reference}</span>
                  <span className="font-medium text-zaro-graphite capitalize">{r.product_type}</span>
                  <span className="rounded-full bg-zaro-ivory px-2.5 py-0.5 text-[0.625rem] uppercase tracking-[0.14em] text-zaro-stone">
                    {STATUS_LABELS[r.status] ?? r.status}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(NEXT_STATUSES[r.status] ?? []).map((next) => (
                    <button
                      key={next}
                      type="button"
                      disabled={busyId === r.id}
                      onClick={() => void transition(r.id, next)}
                      className="inline-flex items-center gap-1 border border-zaro-graphite/15 px-3 py-1.5 text-[0.62rem] uppercase tracking-[0.14em] text-zaro-graphite/80 transition-colors hover:border-zaro-bronze hover:text-zaro-bronze disabled:opacity-40"
                    >
                      {STATUS_LABELS[next] ?? next}
                      <ArrowRight className="size-3" />
                    </button>
                  ))}
                </div>
              </header>
              <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-zaro-graphite line-clamp-3">
                {r.description}
              </p>
              <dl className="mt-4 flex flex-wrap gap-x-7 gap-y-1.5 border-t border-zaro-graphite/8 pt-4 text-xs text-zaro-stone">
                <div className="flex gap-1.5">
                  <dt className="text-zaro-stone/70">From</dt>
                  <dd className="font-medium text-zaro-graphite/80">{r.customer_name}</dd>
                </div>
                {r.customer_email ? <dd>{r.customer_email}</dd> : null}
                {r.customer_phone ? <dd>{r.customer_phone}</dd> : null}
                <dt className="text-zaro-stone/70">Qty</dt>
                <dd className="font-medium text-zaro-graphite/80">{r.quantity}</dd>
                {formatBudgetRange(r.budget_min_minor, r.budget_max_minor, r.currency) && (
                  <>
                    <dt className="text-zaro-stone/70">Budget</dt>
                    <dd className="font-medium text-zaro-graphite/80">
                      {formatBudgetRange(r.budget_min_minor, r.budget_max_minor, r.currency)}
                    </dd>
                  </>
                )}
                <dd className="ms-auto font-mono text-[0.6rem] uppercase text-zaro-stone/70">
                  {new Date(r.created_at).toLocaleDateString()}
                </dd>
              </dl>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}