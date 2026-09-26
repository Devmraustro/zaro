import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewProductPage from "./page";
import { adminFetch } from "@/lib/admin-auth";
import type { AdminProduct } from "@/types/api";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/admin-auth", () => ({
  adminFetch: vi.fn(),
}));

const mockedFetch = vi.mocked(adminFetch);

function created(overrides: Partial<AdminProduct> = {}): AdminProduct {
  return {
    id: "prod-new",
    name: "Atlas dining table",
    slug: "atlas-dining-table",
    product_code: "ZAR-TAB-001",
    description: null,
    category_id: null,
    dimensions: null,
    materials_spec: null,
    selling_price_minor: 0,
    currency: "DZD",
    stock_status: "made_to_order",
    production_time_days: null,
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

const CATEGORIES = [
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
  {
    id: "cat-2",
    name: "Archived line",
    slug: "archived-line",
    description: null,
    sort_order: 1,
    is_active: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

beforeEach(() => {
  mockedFetch.mockReset();
  mockPush.mockReset();
  mockedFetch.mockImplementation((path: string) =>
    path.startsWith("/admin/categories")
      ? Promise.resolve(CATEGORIES)
      : Promise.resolve(created()),
  );
});

function createCall() {
  return mockedFetch.mock.calls.find(
    (c) => c[0] === "/admin/products" && (c[1] as RequestInit | undefined)?.method === "POST",
  );
}

describe("NewProductPage", () => {
  it("only offers active categories and defaults to uncategorised", async () => {
    render(<NewProductPage />);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Dining tables" })).toBeInTheDocument();
    });
    expect(screen.queryByRole("option", { name: "Archived line" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Uncategorised" })).toBeInTheDocument();
  });

  it("creates a draft with a minimal payload and no price call", async () => {
    render(<NewProductPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(createCall()).toBeDefined());
    expect(JSON.parse(String((createCall()![1] as RequestInit).body))).toEqual({
      name: "Atlas dining table",
      category_id: null,
      stock_status: "made_to_order",
      delivery_available: true,
      is_featured: false,
    });
    expect(mockPush).toHaveBeenCalledWith("/admin/products/prod-new?created=1");
    expect(
      mockedFetch.mock.calls.some((c) => String(c[0]).includes("/price")),
    ).toBe(false);
  });

  it("sends is_featured when the merchandising box is ticked", async () => {
    render(<NewProductPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Feature this product/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(createCall()).toBeDefined());
    expect(JSON.parse(String((createCall()![1] as RequestInit).body)).is_featured).toBe(true);
  });

  it("creates then sets the price in a separate audited call", async () => {
    render(<NewProductPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "149000" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-new/price", {
        method: "POST",
        body: JSON.stringify({ selling_price_minor: 14900000 }),
      });
    });
    expect(mockPush).toHaveBeenCalledWith("/admin/products/prod-new?created=1");
  });

  it("sends an explicit null category when a category is chosen", async () => {
    render(<NewProductPage />);
    await waitFor(() => expect(screen.getByRole("option", { name: "Dining tables" })).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "cat-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(createCall()).toBeDefined());
    expect(JSON.parse(String((createCall()![1] as RequestInit).body)).category_id).toBe("cat-1");
  });

  it("blocks a non-numeric price before creating anything", async () => {
    render(<NewProductPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => {
      expect(screen.getByTestId("form-error")).toHaveTextContent("Enter the price as a number");
    });
    expect(createCall()).toBeUndefined();
  });

  it("lands on the workspace with the reason when only the price step is rejected", async () => {
    mockedFetch.mockImplementation((path: string) => {
      if (path.startsWith("/admin/categories")) return Promise.resolve(CATEGORIES);
      if (String(path).endsWith("/price")) {
        return Promise.reject(new Error("You do not have price management permission"));
      }
      return Promise.resolve(created());
    });

    render(<NewProductPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "149000" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith(
        "/admin/products/prod-new?created=1&price_error=You%20do%20not%20have%20price%20management%20permission",
      );
    });
  });

  it("shows the create error and stays on the form when the product is rejected", async () => {
    mockedFetch.mockImplementation((path: string) => {
      if (path.startsWith("/admin/categories")) return Promise.resolve(CATEGORIES);
      return Promise.reject(new Error("A product with that name already exists"));
    });

    render(<NewProductPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas dining table" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => {
      expect(screen.getByTestId("form-error")).toHaveTextContent(
        "A product with that name already exists",
      );
    });
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("keeps the create button disabled until a name is typed", async () => {
    render(<NewProductPage />);
    await waitFor(() => expect(screen.getByLabelText("Name")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: "Create draft" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "A" } });
    expect(screen.getByRole("button", { name: "Create draft" })).toBeEnabled();
  });
});
