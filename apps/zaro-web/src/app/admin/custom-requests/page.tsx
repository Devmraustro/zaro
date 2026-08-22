"use client";

import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatBudgetRange } from "@/lib/format";
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
      <h1 className="text-2xl font-bold text-zaro-black">Custom Requests</h1>

      {error && <div className="mt-6 text-sm text-red-700">{error}</div>}
      {actionError && (
        <div role="alert" className="mt-6 text-sm text-red-700">
          {actionError}
        </div>
      )}
      {!requests && !error && <div className="mt-6 text-sm text-zaro-steel">Loading…</div>}

      {requests && requests.length === 0 && (
        <div className="mt-6 text-sm text-zaro-steel">No custom requests yet.</div>
      )}

      {requests && requests.length > 0 && (
        <div className="mt-6 space-y-3">
          {requests.map((r) => (
            <div key={r.id} className="border border-zaro-ivory-dark bg-white p-4" data-testid="custom-request-row">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-mono text-xs font-semibold text-zaro-bronze">{r.reference}</span>
                  <span className="ml-3 text-sm font-medium text-zaro-black capitalize">
                    {r.product_type}
                  </span>
                  <span className="ml-3 rounded-full bg-zaro-ivory px-2 py-0.5 text-xs uppercase tracking-wider text-zaro-steel">
                    {STATUS_LABELS[r.status] ?? r.status}
                  </span>
                </div>
                <div className="flex gap-2">
                  {(NEXT_STATUSES[r.status] ?? []).map((next) => (
                    <button
                      key={next}
                      type="button"
                      disabled={busyId === r.id}
                      onClick={() => void transition(r.id, next)}
                      className="border border-zaro-ivory-dark px-3 py-1 text-xs uppercase tracking-wider hover:border-zaro-bronze hover:text-zaro-bronze disabled:opacity-40"
                    >
                      → {STATUS_LABELS[next] ?? next}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-zaro-graphite">{r.description}</p>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-zaro-steel">
                <span>{r.customer_name}</span>
                {r.customer_email && <span>{r.customer_email}</span>}
                {r.customer_phone && <span>{r.customer_phone}</span>}
                <span>Qty {r.quantity}</span>
                {formatBudgetRange(r.budget_min_minor, r.budget_max_minor, r.currency) && (
                  <span>Budget: {formatBudgetRange(r.budget_min_minor, r.budget_max_minor, r.currency)}</span>
                )}
                <span>{new Date(r.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
