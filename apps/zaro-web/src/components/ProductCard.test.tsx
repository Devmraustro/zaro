import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProductCard from "./ProductCard";
import type { Product } from "@/types/api";

afterEach(() => {
  vi.unstubAllEnvs();
});

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: "p1",
    name: "Oak Dining Table",
    slug: "oak-dining-table",
    product_code: "ZAR-TAB-001",
    description: null,
    category_id: null,
    dimensions: null,
    materials_spec: null,
    selling_price_minor: 12500000,
    currency: "DZD",
    stock_status: "made_to_order",
    production_time_days: 21,
    delivery_available: true,
    delivery_info: null,
    is_featured: false,
    variants: [],
    media: [],
    ...overrides,
  };
}

describe("ProductCard", () => {
  it("renders name, formatted price and link to detail page", () => {
    render(<ProductCard product={makeProduct()} />);
    const link = screen.getByTestId("product-card");
    expect(link).toHaveAttribute("href", "/shop/oak-dining-table");
    expect(screen.getByText("Oak Dining Table")).toBeInTheDocument();
    expect(screen.getByText("125 000,00 DA")).toBeInTheDocument();
    expect(screen.getByText("Made to order")).toBeInTheDocument();
  });

  it("shows placeholder when there is no media", () => {
    render(<ProductCard product={makeProduct()} />);
    expect(screen.getByText("ZARO")).toBeInTheDocument();
  });

  it("uses the cheapest variant price when variants exist", () => {
    const product = makeProduct({
      selling_price_minor: 10000000,
      variants: [
        {
          id: "v1",
          sku: "SKU-1",
          label: "Standard",
          attributes: null,
          effective_price_minor: 9000000,
          currency: "DZD",
        },
        {
          id: "v2",
          sku: "SKU-2",
          label: "Premium",
          attributes: null,
          effective_price_minor: 11000000,
          currency: "DZD",
        },
      ],
    });
    render(<ProductCard product={product} />);
    expect(screen.getByText("90 000,00 DA")).toBeInTheDocument();
  });

  it("renders cover image with alt text when media exists", () => {
    const product = makeProduct({
      media: [
        {
          id: "m1",
          url_path: "/api/v1/files/m1/public-content",
          media_kind: "image",
          alt_text: "Oak table in a dining room",
          sort_order: 0,
        },
      ],
    });
    render(<ProductCard product={product} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("alt", "Oak table in a dining room");
    expect(img.getAttribute("src")).toContain("/api/v1/files/m1/public-content");
  });

  it("does not duplicate /api/v1 when the API base URL already contains it", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com/api/v1");
    const product = makeProduct({
      media: [
        {
          id: "m1",
          url_path: "/api/v1/files/m1/public-content",
          media_kind: "image",
          alt_text: "Oak table in a dining room",
          sort_order: 0,
        },
      ],
    });
    render(<ProductCard product={product} />);
    const img = screen.getByRole("img");
    expect(img.getAttribute("src")).toBe("https://api.example.com/api/v1/files/m1/public-content");
  });

  it("falls back to raw status label for unknown statuses", () => {
    render(<ProductCard product={makeProduct({ stock_status: "in_stock" })} />);
    expect(screen.getByText("In stock")).toBeInTheDocument();
  });
});
