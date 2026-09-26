import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminCategoriesPage from "./page";
import { adminFetch } from "@/lib/admin-auth";
import type { AdminCategory } from "@/types/api";

vi.mock("@/lib/admin-auth", () => ({
  adminFetch: vi.fn(),
}));

const mockedFetch = vi.mocked(adminFetch);

function category(overrides: Partial<AdminCategory> = {}): AdminCategory {
  return {
    id: "cat-1",
    name: "Dining tables",
    slug: "dining-tables",
    description: "Tables for long dinners",
    sort_order: 0,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("AdminCategoriesPage", () => {
  it("shows an empty state when no categories exist", async () => {
    mockedFetch.mockResolvedValue([]);

    render(<AdminCategoriesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No categories yet")).toBeInTheDocument();
  });

  it("lists categories with their slug and active state", async () => {
    mockedFetch.mockResolvedValue([
      category(),
      category({ id: "cat-2", name: "Chairs", slug: "chairs", is_active: false, sort_order: 1 }),
    ]);

    render(<AdminCategoriesPage />);

    await waitFor(() => {
      expect(screen.getByText("Dining tables")).toBeInTheDocument();
    });
    expect(screen.getByText("/dining-tables")).toBeInTheDocument();
    expect(screen.getByTestId("category-active")).toBeInTheDocument();
    expect(screen.getByText("Chairs")).toBeInTheDocument();
    expect(screen.getByTestId("category-inactive")).toBeInTheDocument();
  });

  it("creates a category with the trimmed name and omits an empty description", async () => {
    mockedFetch.mockResolvedValueOnce([]).mockResolvedValueOnce([category()]);

    render(<AdminCategoriesPage />);
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "  Dining tables  " } });
    fireEvent.click(screen.getByRole("button", { name: "Create category" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/categories", {
        method: "POST",
        body: JSON.stringify({ name: "Dining tables", sort_order: 0 }),
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("category-created")).toBeInTheDocument();
    });
  });

  it("deactivates a category through the PATCH endpoint", async () => {
    mockedFetch.mockResolvedValue([category()]);

    render(<AdminCategoriesPage />);
    await waitFor(() => expect(screen.getByText("Dining tables")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/categories/cat-1", {
        method: "PATCH",
        body: JSON.stringify({ is_active: false }),
      });
    });
  });

  it("sends an explicit null description when the field is cleared", async () => {
    mockedFetch.mockResolvedValue([category()]);

    render(<AdminCategoriesPage />);
    await waitFor(() => expect(screen.getByText("Dining tables")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const nameInput = await screen.findByDisplayValue("Dining tables");
    const form = nameInput.closest("form");
    expect(form).not.toBeNull();

    fireEvent.change(within(form as HTMLFormElement).getByLabelText("Description"), {
      target: { value: "  " },
    });
    fireEvent.click(within(form as HTMLFormElement).getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/categories/cat-1", {
        method: "PATCH",
        body: JSON.stringify({ name: "Dining tables", sort_order: 0, description: null }),
      });
    });
  });

  it("surfaces a load failure", async () => {
    mockedFetch.mockRejectedValue(new Error("Session expired — sign in again"));

    render(<AdminCategoriesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });
    expect(screen.getByText("Session expired — sign in again")).toBeInTheDocument();
  });
});
