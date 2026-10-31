import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KitchenView } from "../features/KitchenView";
import { api } from "../api/client";
import type { ReceiptParsedData, ReceiptCommitResponse } from "../types";

vi.mock("../api/client", () => ({
  api: {
    getInventory: vi.fn(),
    createItem: vi.fn(),
    addInventory: vi.fn(),
    patchInventory: vi.fn(),
    deleteInventory: vi.fn(),
    parseReceipt: vi.fn(),
    commitReceipt: vi.fn(),
  },
}));

describe("KitchenView Receipt Integration", () => {
  const sampleParsedData: ReceiptParsedData = {
    store: "Trader Joe's",
    date: "2026-10-30",
    total: 15.48,
    currency: "USD",
    items: [
      {
        raw_name: "TJ APPLES",
        name: "Apples",
        suggested_location: "pantry",
        quantity: 3,
        unit: "lb",
        price: 4.99,
        category: "Produce",
        include: true,
      },
      {
        raw_name: "TJ OAT MILK",
        name: "Oat Milk",
        suggested_location: "fridge",
        quantity: 1,
        unit: "carton",
        price: 3.49,
        category: "Dairy",
        include: true,
      },
    ],
  };

  const sampleCommitResponse: ReceiptCommitResponse = {
    status: "ok",
    inventory_items_added: 2,
    prices_updated: 2,
    spend_recorded: 15.48,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getInventory as any).mockResolvedValue([]);
    (api.parseReceipt as any).mockResolvedValue(sampleParsedData);
    (api.commitReceipt as any).mockResolvedValue(sampleCommitResponse);
  });

  it("renders Ingest Receipt button and file input with camera capture", () => {
    render(<KitchenView />);
    expect(screen.getByRole("button", { name: /Ingest Receipt/i })).toBeInTheDocument();
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();
    expect(fileInput.getAttribute("accept")).toContain("image/*");
    expect(fileInput.getAttribute("accept")).toContain("application/pdf");
    expect(fileInput.getAttribute("capture")).toBe("environment");
  });

  it("triggers file input when Ingest Receipt button is clicked", async () => {
    const user = userEvent.setup();
    render(<KitchenView />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, "click");

    const ingestBtn = screen.getByRole("button", { name: /Ingest Receipt/i });
    await user.click(ingestBtn);

    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("parses selected receipt file, displays loading state, and opens review modal", async () => {
    let resolveParse: (data: ReceiptParsedData) => void;
    const parsePromise = new Promise<ReceiptParsedData>((res) => {
      resolveParse = res;
    });
    (api.parseReceipt as any).mockReturnValue(parsePromise);

    render(<KitchenView />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    const file = new File(["fake_content"], "receipt.jpg", { type: "image/jpeg" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Loading indicator is shown
    expect(screen.getByText(/Parsing receipt.../i)).toBeInTheDocument();
    expect(api.parseReceipt).toHaveBeenCalledWith(file);

    // Resolve parser
    resolveParse!(sampleParsedData);

    // Review modal opens with parsed data
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Review Ingested Receipt")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Trader Joe's")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Apples")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Parsing receipt.../i)).not.toBeInTheDocument();
  });

  it("supports drag and drop receipt upload", async () => {
    render(<KitchenView />);
    const kitchenView = screen.getByTestId("kitchen-view");

    // Drag enter
    fireEvent.dragEnter(kitchenView, {
      dataTransfer: { items: [{ kind: "file", type: "image/png" }] },
    });
    expect(screen.getByText(/Drop receipt image or PDF here/i)).toBeInTheDocument();

    // Drop file
    const file = new File(["receipt pdf"], "receipt.pdf", { type: "application/pdf" });
    fireEvent.drop(kitchenView, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(api.parseReceipt).toHaveBeenCalledWith(file);
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("refreshes inventory and shows success toast upon committing receipt", async () => {
    const user = userEvent.setup();
    render(<KitchenView />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["receipt-img"], "receipt.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Initial getInventory called once on mount
    expect(api.getInventory).toHaveBeenCalledTimes(1);

    // Click submit in modal
    const commitBtn = screen.getByRole("button", { name: /Add Everything to Kitchen/i });
    await user.click(commitBtn);

    // Modal closes
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // Inventory is refreshed
    expect(api.getInventory).toHaveBeenCalledTimes(2);

    // Success summary toast is visible
    const toast = screen.getByRole("status");
    expect(toast).toHaveTextContent(/Receipt processed: added 2 items, updated 2 prices, recorded \$15\.48 spend/i);

    // Dismiss toast
    const dismissBtn = screen.getByRole("button", { name: /Dismiss message/i });
    await user.click(dismissBtn);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("handles parse error gracefully and calls onError", async () => {
    const onError = vi.fn();
    (api.parseReceipt as any).mockRejectedValue(new Error("OCR engine failed to read receipt"));

    render(<KitchenView onError={onError} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["bad"], "bad.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith("OCR engine failed to read receipt");
    });

    expect(screen.queryByText(/Parsing receipt.../i)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes modal when onClose is triggered without reloading inventory", async () => {
    const user = userEvent.setup();
    render(<KitchenView />);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "receipt.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const cancelBtn = screen.getByRole("button", { name: /Cancel/i });
    await user.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // No extra inventory reload
    expect(api.getInventory).toHaveBeenCalledTimes(1);
  });
});
