import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TrackingLookup from "./TrackingLookup";
import { I18nProvider } from "@/components/I18nProvider";
import { apiFetch } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

const mockedFetch = vi.mocked(apiFetch);

function renderWithProvider() {
  return render(
    <I18nProvider initialLang="en">
      <TrackingLookup />
    </I18nProvider>,
  );
}

const TRACKED = {
  reference: "CR-2026-0001",
  status: "under_review",
  product_type: "dining_table",
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("TrackingLookup", () => {
  it("looks up by reference and email and renders the status card", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValueOnce(TRACKED);

    renderWithProvider();
    await user.type(screen.getByLabelText(/request reference/i), "CR-2026-0001");
    await user.type(screen.getByLabelText(/email or phone/i), "amine@example.com");
    await user.click(screen.getByRole("button", { name: /check status/i }));

    await waitFor(() => {
      expect(screen.getByTestId("tracking-result")).toBeInTheDocument();
    });
    expect(screen.getByText(/CR-2026-0001/)).toBeInTheDocument();
    expect(screen.getAllByText(/under review/i).length).toBeGreaterThan(0);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/custom-requests/track?reference=CR-2026-0001&email=amine%40example.com",
    );
  });

  it("sends a phone contact when the input has no @", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValueOnce(TRACKED);

    renderWithProvider();
    await user.type(screen.getByLabelText(/request reference/i), "cr-2026-0002");
    await user.type(screen.getByLabelText(/email or phone/i), "0555000000");
    await user.click(screen.getByRole("button", { name: /check status/i }));

    await waitFor(() => {
      expect(screen.getByTestId("tracking-result")).toBeInTheDocument();
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/custom-requests/track?reference=CR-2026-0002&phone=0555000000",
    );
  });

  it("normalizes the reference to uppercase and renders cancelled steps", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValueOnce({
      ...TRACKED,
      reference: "CR-2026-0003",
      status: "cancelled",
    });

    renderWithProvider();
    await user.type(screen.getByLabelText(/request reference/i), "cr-2026-0003");
    await user.type(screen.getByLabelText(/email or phone/i), "sara@example.com");
    await user.click(screen.getByRole("button", { name: /check status/i }));

    await waitFor(() => {
      expect(screen.getByTestId("tracking-result")).toBeInTheDocument();
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/custom-requests/track?reference=CR-2026-0003&email=sara%40example.com",
    );
    expect(screen.getAllByText(/cancelled/i).length).toBeGreaterThan(0);
  });

  it("blocks lookup when reference or contact is missing", async () => {
    const user = userEvent.setup();
    renderWithProvider();
    await user.type(screen.getByLabelText(/request reference/i), "CR");
    await user.click(screen.getByRole("button", { name: /check status/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter your reference and the email or phone used when submitting.",
    );
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("shows a not-found message when the API returns 404", async () => {
    const user = userEvent.setup();
    mockedFetch.mockRejectedValueOnce(Object.assign(new Error("HTTP 404"), { status: 404 }));

    renderWithProvider();
    await user.type(screen.getByLabelText(/request reference/i), "CR-2026-0009");
    await user.type(screen.getByLabelText(/email or phone/i), "nobody@example.com");
    await user.click(screen.getByRole("button", { name: /check status/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "We couldn't find a matching request.",
      );
    });
    expect(screen.queryByTestId("tracking-result")).not.toBeInTheDocument();
  });
});