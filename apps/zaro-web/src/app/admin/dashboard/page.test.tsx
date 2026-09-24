import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminDashboardPage from "./page";
import { adminFetch, hasActiveSession } from "@/lib/admin-auth";

vi.mock("@/lib/admin-auth", () => ({
  adminFetch: vi.fn(),
  hasActiveSession: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const mockedFetch = vi.mocked(adminFetch);
const mockedHasSession = vi.mocked(hasActiveSession);

beforeEach(() => {
  mockedFetch.mockReset();
  mockedHasSession.mockReset();
  mockedHasSession.mockResolvedValue(true);
});

describe("AdminDashboardPage", () => {
  it("renders KPI cards and recent requests from the summary", async () => {
    mockedFetch.mockResolvedValue({
      custom_requests: {
        total: 12,
        by_status: { submitted: 3, under_review: 1 },
        pending: 4,
        this_week: 5,
      },
      recent_requests: [
        {
          id: "req-1",
          reference: "CR-2026-0012",
          status: "submitted",
          product_type: "dining_table",
          customer_name: "Amine Belkacem",
          wilaya: "16",
          created_at: "2026-09-16T00:00:00Z",
        },
      ],
      customers_total: 40,
      products: { total: 15, active: 9 },
    });

    render(<AdminDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Custom requests")).toBeInTheDocument();
    });
    expect(screen.getAllByText("12").length).toBeGreaterThan(0);
    expect(screen.getByText("4 pending")).toBeInTheDocument();
    expect(screen.getByText("New this week")).toBeInTheDocument();
    expect(screen.getAllByText("5").length).toBeGreaterThan(0);
    expect(screen.getByText("Customers")).toBeInTheDocument();
    expect(screen.getAllByText("40").length).toBeGreaterThan(0);
    expect(screen.getByText("9 live")).toBeInTheDocument();
    expect(screen.getByText("Recent requests")).toBeInTheDocument();
    expect(screen.getByText("CR-2026-0012")).toBeInTheDocument();
    expect(mockedFetch).toHaveBeenCalledWith("/admin/dashboard");
  });

  it("renders only the metrics the role is allowed to read", async () => {
    mockedFetch.mockResolvedValue({
      products: { total: 3, active: 1 },
    });

    render(<AdminDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Products")).toBeInTheDocument();
    });
    expect(screen.getByText("1 live")).toBeInTheDocument();
    expect(screen.queryByText("Customers")).not.toBeInTheDocument();
    expect(screen.queryByText("Recent requests")).not.toBeInTheDocument();
  });

  it("redirects to /admin when no active session exists", async () => {
    mockedHasSession.mockResolvedValue(false);

    render(<AdminDashboardPage />);

    await waitFor(() => {
      expect(mockedFetch).not.toHaveBeenCalled();
    });
  });
});