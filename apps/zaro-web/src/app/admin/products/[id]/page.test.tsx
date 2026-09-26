import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminProductWorkspacePage from "./page";
import { adminFetch } from "@/lib/admin-auth";
import type { AdminProduct } from "@/types/api";

const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "prod-1" }),
  useRouter: () => ({ push: mockPush, replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/lib/admin-auth", () => ({
  adminFetch: vi.fn(),
}));

// The media panel has its own upload/list lifecycle; it is covered separately.
vi.mock("@/components/admin/catalog/ProductMediaManager", () => ({
  default: ({ productId }: { productId: string }) => (
    <div data-testid="media-manager">{`media:${productId}`}</div>
  ),
}));

const mockedFetch = vi.mocked(adminFetch);

function product(overrides: Partial<AdminProduct> = {}): AdminProduct {
  return {
    id: "prod-1",
    name: "Atlas dining table",
    slug: "atlas-dining-table",
    product_code: "ZAR-TAB-001",
    description: "Solid oak dining table",
    category_id: "cat-1",
    dimensions: { width: 180, height: 75, depth: 90, unit: "cm" },
    materials_spec: [{ name: "Oak", grade: null, finish: "natural" }],
    selling_price_minor: 14900000,
    currency: "DZD",
    stock_status: "made_to_order",
    production_time_days: 45,
    delivery_available: true,
    delivery_info: "Delivered in 2–4 weeks",
    is_featured: false,
    variants: [
      {
        id: "v-1",
        sku: "ZAR-TAB-001-V01",
        label: "180cm / natural oak",
        attributes: null,
        price_override_minor: null,
        is_active: true,
        sort_order: 0,
      },
    ],
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
];

/** Route by URL: the workspace hits the product, the category list, then actions. */
function mockWorkspace(result: AdminProduct) {
  mockedFetch.mockImplementation((path: string) => {
    if (path === "/admin/products/prod-1") return Promise.resolve(result);
    if (path.startsWith("/admin/categories")) return Promise.resolve(CATEGORIES);
    return Promise.resolve(result);
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
  mockPush.mockReset();
  for (const key of Array.from(mockSearchParams.keys())) mockSearchParams.delete(key);
});

describe("AdminProductWorkspacePage", () => {
  it("shows a load failure instead of a blank workspace", async () => {
    mockedFetch.mockRejectedValue(new Error("Product not found"));

    render(<AdminProductWorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });
    expect(screen.getByText("Product not found")).toBeInTheDocument();
  });

  it("renders the code, status, dimensions, price and variants from the API", async () => {
    mockWorkspace(product());

    render(<AdminProductWorkspacePage />);

    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());
    expect(screen.getByTestId("status-draft")).toHaveTextContent("Draft");
    expect(screen.getByDisplayValue("180")).toBeInTheDocument();
    expect(screen.getByText("ZAR-TAB-001-V01")).toBeInTheDocument();
    expect(screen.getByTestId("media-manager")).toHaveTextContent("media:prod-1");
  });

  it("sends is_featured in the details PATCH when the checkbox changes", async () => {
    mockWorkspace(product());

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    const featured = screen.getAllByRole("checkbox", { name: /Featured/ })[0] as HTMLInputElement;
    expect(featured.checked).toBe(false);
    fireEvent.click(featured);
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));

    await waitFor(() => {
      const call = mockedFetch.mock.calls.find(
        (c) => c[0] === "/admin/products/prod-1" && (c[1] as RequestInit | undefined)?.method === "PATCH",
      );
      expect(call).toBeDefined();
      const body = JSON.parse(String((call![1] as RequestInit).body)) as Record<string, unknown>;
      expect(body.is_featured).toBe(true);
    });
  });

  /** Read the production_time_days sent in the details PATCH. */
  async function savedProductionTime(): Promise<unknown> {
    const call = mockedFetch.mock.calls.find(
      (c) => c[0] === "/admin/products/prod-1" && (c[1] as RequestInit | undefined)?.method === "PATCH",
    );
    expect(call).toBeDefined();
    const body = JSON.parse(String((call![1] as RequestInit).body)) as Record<string, unknown>;
    return body.production_time_days;
  }

  it("sends an explicit null when the admin clears the production time", async () => {
    mockWorkspace(product({ production_time_days: 30 }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    const field = screen.getByLabelText("Production time (days)") as HTMLInputElement;
    expect(field.value).toBe("30");

    fireEvent.change(field, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));

    // Must be present-and-null, not an omitted key: the API reads an absent key
    // as "leave unchanged", which would silently keep 30 in the database.
    await waitFor(async () => {
      expect(await savedProductionTime()).toBeNull();
    });
    const call = mockedFetch.mock.calls.find(
      (c) => c[0] === "/admin/products/prod-1" && (c[1] as RequestInit | undefined)?.method === "PATCH",
    );
    const body = JSON.parse(String((call![1] as RequestInit).body)) as Record<string, unknown>;
    expect("production_time_days" in body).toBe(true);
  });

  it("sends the integer when the admin edits the production time", async () => {
    mockWorkspace(product({ production_time_days: 30 }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Production time (days)"), { target: { value: "45" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));

    await waitFor(async () => {
      expect(await savedProductionTime()).toBe(45);
    });
  });

  it("keeps the existing production time when the field is untouched", async () => {
    mockWorkspace(product({ production_time_days: 30 }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    // Edit an unrelated field only; production time must round-trip unchanged,
    // never be cleared as a side effect.
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas table" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));

    await waitFor(async () => {
      expect(await savedProductionTime()).toBe(30);
    });
  });

  it("clears a production time that was already null without error", async () => {
    mockWorkspace(product({ production_time_days: null }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    const field = screen.getByLabelText("Production time (days)") as HTMLInputElement;
    expect(field.value).toBe("");

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Atlas table" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));

    await waitFor(async () => {
      expect(await savedProductionTime()).toBeNull();
    });
    expect(await screen.findByText(/Saved/i)).toBeInTheDocument();
  });

  it("publishes a draft through the publish endpoint", async () => {
    mockWorkspace(product());

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/publish", { method: "POST" });
    });
  });

  it("surfaces the publish validation error for a product with no price", async () => {
    mockWorkspace(product({ selling_price_minor: 0 }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    mockedFetch.mockImplementation((path: string, options?: RequestInit) => {
      if (path === "/admin/products/prod-1/publish") {
        return Promise.reject(new Error("Set a positive selling price before publishing"));
      }
      if (path.startsWith("/admin/categories")) return Promise.resolve(CATEGORIES);
      return Promise.resolve(options === undefined ? product({ selling_price_minor: 0 }) : product());
    });

    fireEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(screen.getByTestId("form-error")).toHaveTextContent(
        "Set a positive selling price before publishing",
      );
    });
  });

  it("converts the major-unit price input into minor units", async () => {
    mockWorkspace(product());

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "200000.50" } });
    fireEvent.click(screen.getByRole("button", { name: "Update price" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/price", {
        method: "POST",
        body: JSON.stringify({ selling_price_minor: 20000050 }),
      });
    });
  });

  it("rejects a non-numeric price before calling the API", async () => {
    mockWorkspace(product());

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    mockedFetch.mockClear();
    fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Update price" }));

    await waitFor(() => {
      expect(screen.getByTestId("form-error")).toHaveTextContent("Enter the price as a number");
    });
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("adds a variant and lets the API generate the SKU", async () => {
    mockWorkspace(product());

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("New variant"), { target: { value: "220cm / walnut" } });
    fireEvent.click(screen.getByRole("button", { name: "Add variant" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/variants", {
        method: "POST",
        body: JSON.stringify({ label: "220cm / walnut" }),
      });
    });
  });

  it("hides publish for a live product and explains the archived state", async () => {
    mockWorkspace(product({ status: "archived" }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
    expect(screen.getByText("Archived products stay read-only in the catalog.")).toBeInTheDocument();
  });

  it("links to the public page only once a product is live", async () => {
    mockWorkspace(product({ status: "active" }));

    render(<AdminProductWorkspacePage />);
    await waitFor(() => expect(screen.getByText("ZAR-TAB-001")).toBeInTheDocument());

    expect(screen.getByText("View public page →")).toHaveAttribute("href", "/products/atlas-dining-table");
    expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
  });

  it("confirms the draft state after creation and explains a price that failed", async () => {
    mockSearchParams.set("created", "1");
    mockSearchParams.set("price_error", "You do not have price management permission");
    mockWorkspace(product({ selling_price_minor: 0 }));

    render(<AdminProductWorkspacePage />);

    await waitFor(() => expect(screen.getByTestId("created-notice")).toBeInTheDocument());
    expect(screen.getByTestId("form-error")).toHaveTextContent(
      "the price was not saved: You do not have price management permission",
    );
  });
});
