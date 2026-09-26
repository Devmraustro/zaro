import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProductMediaManager from "./ProductMediaManager";
import { adminFetch, adminUpload } from "@/lib/admin-auth";
import type { AdminMedia } from "@/types/api";

vi.mock("@/lib/admin-auth", () => ({
  adminFetch: vi.fn(),
  adminUpload: vi.fn(),
}));

const mockedFetch = vi.mocked(adminFetch);
const mockedUpload = vi.mocked(adminUpload);

function media(overrides: Partial<AdminMedia> = {}): AdminMedia {
  return {
    id: "asset-1",
    media_kind: "hero",
    alt_text: "Front view",
    sort_order: 0,
    original_filename: "front.png",
    content_type: "image/png",
    size_bytes: 2048,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function mockMediaList(items: AdminMedia[]) {
  mockedFetch.mockResolvedValue(items);
}

/** A second, visually distinct card so accessible names stay unique. */
function second(): AdminMedia {
  return media({
    id: "asset-2",
    media_kind: "gallery",
    alt_text: "Side view",
    sort_order: 1,
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
  mockedUpload.mockReset();
  mockedUpload.mockResolvedValue(media());
});

function fileInput(): HTMLInputElement {
  return within(screen.getByTestId("media-upload-form")).getByLabelText("Image") as HTMLInputElement;
}

function card(id: string): HTMLElement {
  return screen.getByTestId(`media-card-${id}`);
}

async function pickFile(name = "shot.png") {
  const file = new File(["binary"], name, { type: "image/png" });
  fireEvent.change(fileInput(), { target: { files: [file] } });
  return file;
}

describe("ProductMediaManager", () => {
  it("shows the empty state when a product has no images", async () => {
    mockMediaList([]);

    render(<ProductMediaManager productId="prod-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No images yet")).toBeInTheDocument();
  });

  it("loads media from the product media endpoint", async () => {
    mockMediaList([media()]);

    render(<ProductMediaManager productId="prod-1" />);

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/media");
    });
    expect(within(card("asset-1")).getByText("Front view")).toBeInTheDocument();
    expect(within(card("asset-1")).getByText("image/png · 2.0 KB")).toBeInTheDocument();
  });

  it("uploads a file with the chosen kind, alt text and next sort order", async () => {
    mockMediaList([media({ sort_order: 0 }), second()]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(within(card("asset-1")).getAllByText("Front view")[0]).toBeInTheDocument());

    await pickFile();
    const form = screen.getByTestId("media-upload-form");
    fireEvent.change(within(form).getByLabelText("Kind"), { target: { value: "lifestyle" } });
    fireEvent.change(within(form).getByLabelText("Alt text"), { target: { value: "In a room" } });
    const submit = within(form).getByRole("button", { name: "Upload image" });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.submit(form);

    await waitFor(() => expect(mockedUpload).toHaveBeenCalled());
    const formData = mockedUpload.mock.calls[0]![1] as FormData;
    expect(mockedUpload.mock.calls[0]![0]).toBe("/admin/products/prod-1/media");
    expect(formData.get("media_kind")).toBe("lifestyle");
    expect(formData.get("alt_text")).toBe("In a room");
    expect(formData.get("sort_order")).toBe("2");
  });

  it("never offers video as an upload kind", async () => {
    mockMediaList([]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());

    const options = within(screen.getByLabelText("Kind")).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["Hero", "Gallery", "Detail", "Lifestyle"]);
  });

  it("patches kind and alt text from the edit form", async () => {
    mockMediaList([media()]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(within(card("asset-1")).getAllByText("Front view")[0]).toBeInTheDocument());

    fireEvent.click(within(card("asset-1")).getByRole("button", { name: "Edit details" }));
    fireEvent.change(within(card("asset-1")).getByLabelText("Alt text"), {
      target: { value: "Angled view" },
    });
    fireEvent.change(within(card("asset-1")).getByLabelText("Image kind"), {
      target: { value: "gallery" },
    });
    fireEvent.click(within(card("asset-1")).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/media/asset-1", {
        method: "PATCH",
        body: JSON.stringify({ media_kind: "gallery", alt_text: "Angled view" }),
      });
    });
  });

  it("sends a null alt_text when the field is emptied", async () => {
    mockMediaList([media()]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(within(card("asset-1")).getAllByText("Front view")[0]).toBeInTheDocument());

    fireEvent.click(within(card("asset-1")).getByRole("button", { name: "Edit details" }));
    fireEvent.change(within(card("asset-1")).getByLabelText("Alt text"), { target: { value: "   " } });
    fireEvent.click(within(card("asset-1")).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const call = mockedFetch.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PATCH");
      expect(JSON.parse(String((call![1] as RequestInit).body)).alt_text).toBeNull();
    });
  });

  it("deletes an image through the delete endpoint", async () => {
    mockMediaList([media()]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(within(card("asset-1")).getAllByText("Front view")[0]).toBeInTheDocument());

    fireEvent.click(within(card("asset-1")).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith("/admin/products/prod-1/media/asset-1", {
        method: "DELETE",
      });
    });
  });

  it("swaps sort_order with the neighbour when reordering", async () => {
    mockMediaList([media({ sort_order: 0 }), second()]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(within(card("asset-1")).getAllByText("Front view")[0]).toBeInTheDocument());

    fireEvent.click(within(card("asset-1")).getByRole("button", { name: "Move hero image down" }));

    await waitFor(() => {
      const patches = mockedFetch.mock.calls.filter(
        (c) => (c[1] as RequestInit | undefined)?.method === "PATCH",
      );
      expect(patches).toHaveLength(2);
      const bodies = patches.map((c) => JSON.parse(String((c[1] as RequestInit).body)) as { sort_order: number });
      expect(bodies.map((b) => b.sort_order).sort()).toEqual([0, 1]);
    });
  });

  it("disables reordering at the list edges", async () => {
    mockMediaList([media({ sort_order: 0 }), second()]);

    render(<ProductMediaManager productId="prod-1" />);
    await waitFor(() => expect(within(card("asset-1")).getAllByText("Front view")[0]).toBeInTheDocument());

    expect(within(card("asset-1")).getByRole("button", { name: "Move hero image up" })).toBeDisabled();
    expect(within(card("asset-1")).getByRole("button", { name: "Move hero image down" })).toBeEnabled();
    expect(within(card("asset-2")).getByRole("button", { name: "Move gallery image up" })).toBeEnabled();
    expect(within(card("asset-2")).getByRole("button", { name: "Move gallery image down" })).toBeDisabled();
  });

  it("reports an upload failure through onError", async () => {
    mockMediaList([]);
    mockedUpload.mockRejectedValue(new Error("File exceeds the 5 MB limit"));
    const onError = vi.fn();

    render(<ProductMediaManager productId="prod-1" onError={onError} />);
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());

    await pickFile();
    const form = screen.getByTestId("media-upload-form");
    await waitFor(() => expect(within(form).getByRole("button", { name: "Upload image" })).toBeEnabled());
    fireEvent.submit(form);

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith("File exceeds the 5 MB limit");
    });
  });
});
