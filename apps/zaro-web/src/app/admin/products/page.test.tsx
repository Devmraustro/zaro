import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminProductsPage from "./page";
import { adminFetch } from "@/lib/admin-auth";
import type { AdminProduct, AdminProductList } from "@/types/api";

vi.mock("@/lib/admin-auth", () => ({
  adminFetch: vi.fn(),
}));

const mockedFetch = vi.mocked(adminFetch);

function product(overrides: Partial<AdminProduct> = {}): AdminProduct {
  return {
    id: "prod-1",
    name: "Atlas dining table",
    slug: "atlas-dining-table",
    product_code: "ZAR-TAB-001",
    description: "Solid oak",
    category_id: "cat-1",
    dimensions: { width: 180, unit: "cm" },
    materials_spec: [{ name: "Oak" }],
    selling_price_minor: 14900000,
    currency: "DZD",
    stock_status: "made_to_order",
    production_time_days: 45,
    delivery_available: true,
    delivery_info: null,
    is_featured: false,
    variants: [],
    media: [],
    status: "draft",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function list(items: AdminProduct[], overrides: Partial<AdminProductList> = {}): AdminProductList {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    has_next: false,
    has_previous: false,
    ...overrides,
  };
}

beforeEach(() => {
  mockedFetch.mockReset();
});

/** Route the two list-time calls (products, then categories) by URL. */
function mockList(result: AdminProductList, categories: unknown[] = []) {
  mockedFetch.mockImplementation((path: string) => {
    if (path.startsWith("/admin/categories")) return Promise.resolve(categories);
    return Promise.resolve(result);
  });
}

describe("AdminProductsPage", () => {
  it("shows a create-first empty state with no fabricated rows", async () => {
    mockList(list([]));

    render(<AdminProductsPage />);

    await waitFor(() => {
      expect(screen.getByText("No products yet")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("status-draft")).not.toBeInTheDocument();
  });

  it("renders product, price, stock and status columns", async () => {
    mockList(list([product()]));

    render(<AdminProductsPage />);

    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());
    expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument();
    expect(screen.getByText("149 000,00 DA")).toBeInTheDocument();
    expect(screen.getByText("Made to order")).toBeInTheDocument();
    expect(screen.getByTestId("status-draft")).toHaveTextContent("Draft");
  });

  it("labels an active product as Published and shows the featured badge", async () => {
    mockList(list([product({ status: "active", is_featured: true })]));

    render(<AdminProductsPage />);

    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());
    expect(screen.getByTestId("status-active")).toHaveTextContent("Published");
    expect(screen.getByTestId("featured-badge")).toBeInTheDocument();
  });

  it("flags a product with no price as not set", async () => {
    mockList(list([product({ selling_price_minor: 0 })]));

    render(<AdminProductsPage />);

    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());
    expect(screen.getByText("Not set")).toBeInTheDocument();
  });

  it("requests a page size the API accepts and appends the search term", async () => {
    mockList(list([product()]));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search products by name"), {
      target: { value: "  atlas  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      const calls = mockedFetch.mock.calls.map((c) => String(c[0]));
      expect(calls).toContain("/admin/products?page=1&page_size=20&search=atlas");
    });
  });

  it("sends the status filter to the API", async () => {
    mockList(list([product()]));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Filter by status"), { target: { value: "archived" } });

    await waitFor(() => {
      const calls = mockedFetch.mock.calls.map((c) => String(c[0]));
      expect(calls).toContain("/admin/products?page=1&page_size=20&status=archived");
    });
  });

  it("toggles featured through the product PATCH endpoint", async () => {
    mockList(list([product()]));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Feature" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1", {
        method: "PATCH",
        body: JSON.stringify({ is_featured: true }),
      });
    });
  });

  it("publishes a draft through the publish endpoint", async () => {
    mockList(list([product()]));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/publish", { method: "POST" });
    });
  });

  it("requires a second click before archiving a live product", async () => {
    mockList(list([product({ status: "active" })]));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(mockedFetch).not.toHaveBeenCalledWith("/admin/products/prod-1/archive", { method: "POST" });

    fireEvent.click(screen.getByRole("button", { name: "Confirm archive" }));
    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/archive", { method: "POST" });
    });
  });

  it("surfaces the API message when a write is forbidden", async () => {
    mockedFetch.mockImplementation((path: string) => {
      if (path.startsWith("/admin/categories")) return Promise.resolve([]);
      if (path.startsWith("/admin/products?")) {
        return Promise.resolve(list([product({ status: "draft", selling_price_minor: 0 })]));
      }
      return Promise.reject(new Error("Set a positive selling price before publishing"));
    });

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(screen.getByTestId("form-error")).toHaveTextContent(
        "Set a positive selling price before publishing",
      );
    });
  });

  it("disables pagination controls using the server's has_next / has_previous flags", async () => {
    mockList(list([product()], { total: 45, has_previous: true, has_next: true, page: 2 }));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
    expect(screen.getByText("Showing 21–40 of 45")).toBeInTheDocument();
  });

  it("offers a way to clear filters when a filtered search finds nothing", async () => {
    mockList(list([]));

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Filter by status"), { target: { value: "draft" } });

    await waitFor(() => {
      expect(screen.getByText("No matching products")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
  });

  it("resolves the category name and falls back to Uncategorised", async () => {
    mockList(
      list([
        product({ category_id: "cat-1" }),
        product({ id: "prod-2", name: "Mystery item", category_id: null }),
      ]),
      [
        {
          id: "cat-1",
          name: "Dining tables",
          slug: "dining-tables",
          description: null,
          sort_order: 0,
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    );

    render(<AdminProductsPage />);
    await waitFor(() => expect(screen.getByText("Atlas dining table")).toBeInTheDocument());

    expect(screen.getByText("Dining tables")).toBeInTheDocument();
    expect(screen.getByText("Uncategorised")).toBeInTheDocument();
  });
});
