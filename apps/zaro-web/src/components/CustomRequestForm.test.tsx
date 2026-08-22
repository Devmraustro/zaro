import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CustomRequestForm from "./CustomRequestForm";
import { apiFetch } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

const mockedFetch = vi.mocked(apiFetch);

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  // user-event calls must be sequential; concurrent typing corrupts state.
  await user.type(screen.getByLabelText(/full name/i), "Amine Belkacem");
  await user.type(screen.getByLabelText(/email/i), "amine@example.com");
  await user.selectOptions(screen.getByLabelText(/product type/i), "table");
  await user.type(screen.getByLabelText(/describe your project/i), "A large oak dining table for 8 people");
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("CustomRequestForm", () => {
  it("submits a valid payload and shows the reference", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValueOnce({
      id: "cr1",
      reference: "CR-2026-0001",
      product_type: "table",
      description: "A large oak dining table for 8 people",
      desired_dimensions: null,
      materials: null,
      colors: null,
      finish: null,
      quantity: 1,
      budget_min_minor: null,
      budget_max_minor: null,
      currency: "DZD",
      status: "submitted",
      created_at: "2026-08-21T00:00:00Z",
      updated_at: "2026-08-21T00:00:00Z",
    });

    render(<CustomRequestForm />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /send request/i }));

    await waitFor(() => {
      expect(screen.getByTestId("request-success")).toBeInTheDocument();
    });
    expect(screen.getByText("CR-2026-0001")).toBeInTheDocument();

    expect(mockedFetch).toHaveBeenCalledWith("/custom-requests", {
      method: "POST",
      body: expect.any(String),
    });
    const payload = JSON.parse((mockedFetch.mock.calls[0]?.[1]?.body as string | undefined) ?? "{}");
    expect(payload.full_name).toBe("Amine Belkacem");
    expect(payload.product_type).toBe("table");
    expect(payload.description).toBe("A large oak dining table for 8 people");
    expect(payload.budget_min_minor).toBeNull();
  });

  it("converts budget dinar input to minor units", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValueOnce({
      id: "cr2",
      reference: "CR-2026-0002",
      product_type: "desk",
      description: "Standing desk in walnut and steel",
      desired_dimensions: null,
      materials: null,
      colors: null,
      finish: null,
      quantity: 1,
      budget_min_minor: 8000000,
      budget_max_minor: 12000000,
      currency: "DZD",
      status: "submitted",
      created_at: "2026-08-21T00:00:00Z",
      updated_at: "2026-08-21T00:00:00Z",
    });

    render(<CustomRequestForm />);
    await user.type(screen.getByLabelText(/full name/i), "Sara H.");
    await user.selectOptions(screen.getByLabelText(/product type/i), "desk");
    await user.type(screen.getByLabelText(/describe your project/i), "Standing desk in walnut and steel");
    await user.type(screen.getByLabelText(/budget min/i), "80000");
    await user.type(screen.getByLabelText(/budget max/i), "120000");
    await user.click(screen.getByRole("button", { name: /send request/i }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalled();
    });
    const payload = JSON.parse((mockedFetch.mock.calls[0]?.[1]?.body as string | undefined) ?? "{}");
    expect(payload.budget_min_minor).toBe(8000000);
    expect(payload.budget_max_minor).toBe(12000000);
  });

  it("blocks submission when description is too short", async () => {
    const user = userEvent.setup();
    render(<CustomRequestForm />);
    await user.type(screen.getByLabelText(/full name/i), "A B");
    await user.type(screen.getByLabelText(/describe your project/i), "short");
    await user.click(screen.getByRole("button", { name: /send request/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Please describe your project in at least 10 characters.",
    );
    expect(mockedFetch).not.toHaveBeenCalled();
    expect(screen.queryByTestId("request-success")).not.toBeInTheDocument();
  });

  it("shows an error message when the API rejects the request", async () => {
    const user = userEvent.setup();
    mockedFetch.mockRejectedValueOnce(new Error("Too many requests"));

    render(<CustomRequestForm />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /send request/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Too many requests");
    });
    expect(screen.queryByTestId("request-success")).not.toBeInTheDocument();
  });
});
