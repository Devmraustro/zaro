import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ProductImage from "./ProductImage";

describe("ProductImage", () => {
  it("renders the photograph with alt text when a source exists", () => {
    render(<ProductImage src="/api/v1/files/m1/public-content" alt="Oak table" />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/api/v1/files/m1/public-content");
    expect(img).toHaveAttribute("alt", "Oak table");
    expect(img).not.toHaveAttribute("aria-hidden");
  });

  it("marks final images as priority (eager + fetchpriority high)", () => {
    render(<ProductImage src="/m.jpg" alt="Hero" priority />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("loading", "eager");
    expect(img.getAttribute("fetchpriority")).toBe("high");
  });

  it("lazy-loads below-the-fold media by default", () => {
    render(<ProductImage src="/m.jpg" alt="Card" />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img.getAttribute("fetchpriority")).toBeNull();
  });

  it("renders decorative thumbnails with an empty alt", () => {
    const { container } = render(<ProductImage src="/t1.jpg" alt="Thumb" decorative />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img!.getAttribute("alt")).toBe("");
  });

  it("falls back to the line-art placeholder when there is no source", () => {
    const { container } = render(<ProductImage src={null} alt="Empty product" />);
    expect(screen.getByText("ZARO")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("img", { name: "Empty product" })).toBeInTheDocument();
  });

  it("falls back to the placeholder when image load fails", () => {
    const { container } = render(<ProductImage src="/broken.jpg" alt="Broken" />);
    const img = screen.getByRole("img");
    fireEvent.error(img);
    expect(screen.getByText("ZARO")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });
});