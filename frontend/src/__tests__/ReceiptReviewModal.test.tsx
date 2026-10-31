import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReceiptReviewModal } from "../features/ReceiptReviewModal";
import { api } from "../api/client";
import type { ReceiptParsedData, ReceiptCommitResponse } from "../types";

vi.mock("../api/client", () => ({
  api: {
    commitReceipt: vi.fn(),
  },
}));

describe("ReceiptReviewModal", () => {
  const sampleData: ReceiptParsedData = {
    store: "Trader Joe's",
    date: "2026-10-30",
    total: 15.48,
    currency: "USD",
    items: [
      {
        raw_name: "TJ ORG BANANAS",
        name: "Organic Bananas",
        suggested_location: "pantry",
        quantity: 2,
        unit: "bunch",
        price: 3.98,
        category: "Produce",
        include: true,
      },
      {
        raw_name: "TJ ALMOND MILK",
        name: "Almond Milk",
        suggested_location: "fridge",
        quantity: 1,
        unit: "carton",
        price: 2.99,
        category: "Dairy",
        include: true,
      },
    ],
  };

  const mockResponse: ReceiptCommitResponse = {
    status: "ok",
    inventory_items_added: 2,
    prices_updated: 2,
    spend_recorded: 15.48,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders parsed receipt items and allows changing location", async () => {
    const user = userEvent.setup();
    const mockData: ReceiptParsedData = {
      store: "Walmart",
      date: "2026-10-30",
      total: 3.48,
      currency: "USD",
      items: [
        {
          raw_name: "GV 2% MILK 1GAL",
          name: "2% Milk",
          suggested_location: "fridge",
          quantity: 1,
          unit: "gal",
          price: 3.48,
          category: "Dairy",
          include: true,
        },
      ],
    };

    const onClose = vi.fn();
    const onCommitted = vi.fn();

    render(
      <ReceiptReviewModal
        data={mockData}
        onClose={onClose}
        onCommitted={onCommitted}
      />
    );

    // Initial render checks
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Walmart")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-10-30")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2% Milk")).toBeInTheDocument();
    expect(screen.getAllByDisplayValue("3.48").length).toBeGreaterThanOrEqual(1);

    // Change location to freezer
    const locationSelect = screen.getByRole("combobox", { name: /location/i });
    expect(locationSelect).toHaveValue("fridge");
    await user.selectOptions(locationSelect, "freezer");
    expect(locationSelect).toHaveValue("freezer");
  });

  it("allows modifying item details (name, quantity, unit, price)", async () => {
    const user = userEvent.setup();
    render(
      <ReceiptReviewModal
        data={sampleData}
        onClose={vi.fn()}
        onCommitted={vi.fn()}
      />
    );

    const nameInput = screen.getByDisplayValue("Organic Bananas");
    await user.clear(nameInput);
    await user.type(nameInput, "Bananas (Fair Trade)");
    expect(screen.getByDisplayValue("Bananas (Fair Trade)")).toBeInTheDocument();

    const qtyInputs = screen.getAllByRole("spinbutton", { name: /quantity/i });
    await user.clear(qtyInputs[0]);
    await user.type(qtyInputs[0], "3");
    expect(qtyInputs[0]).toHaveValue(3);

    const unitInputs = screen.getAllByRole("textbox", { name: /unit/i });
    await user.clear(unitInputs[0]);
    await user.type(unitInputs[0], "lbs");
    expect(unitInputs[0]).toHaveValue("lbs");

    const priceInputs = screen.getAllByRole("spinbutton", { name: /price/i });
    await user.clear(priceInputs[0]);
    await user.type(priceInputs[0], "4.50");
    expect(priceInputs[0]).toHaveValue(4.5);
  });

  it("allows toggling item inclusion", async () => {
    const user = userEvent.setup();
    vi.mocked(api.commitReceipt).mockResolvedValueOnce(mockResponse);

    const onCommitted = vi.fn();
    const onClose = vi.fn();

    render(
      <ReceiptReviewModal
        data={sampleData}
        onClose={onClose}
        onCommitted={onCommitted}
      />
    );

    const includeCheckboxes = screen.getAllByRole("checkbox", {
      name: /include/i,
    });
    expect(includeCheckboxes[0]).toBeChecked();
    expect(includeCheckboxes[1]).toBeChecked();

    // Uncheck first item
    await user.click(includeCheckboxes[0]);
    expect(includeCheckboxes[0]).not.toBeChecked();

    // Commit
    const submitBtn = screen.getByRole("button", {
      name: /Add Everything to Kitchen/i,
    });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(api.commitReceipt).toHaveBeenCalledWith(
        expect.objectContaining({
          items: [
            expect.objectContaining({
              name: "Organic Bananas",
              include_inventory: false,
              include_price: false,
            }),
            expect.objectContaining({
              name: "Almond Milk",
              include_inventory: true,
              include_price: true,
            }),
          ],
        })
      );
    });
  });

  it("allows adding and removing line items", async () => {
    const user = userEvent.setup();
    render(
      <ReceiptReviewModal
        data={sampleData}
        onClose={vi.fn()}
        onCommitted={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("Organic Bananas")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Almond Milk")).toBeInTheDocument();

    // Remove first item
    const removeButtons = screen.getAllByRole("button", {
      name: /remove item/i,
    });
    await user.click(removeButtons[0]);

    expect(screen.queryByDisplayValue("Organic Bananas")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("Almond Milk")).toBeInTheDocument();

    // Add new line item
    const addBtn = screen.getByRole("button", { name: /\+ Add Line Item/i });
    await user.click(addBtn);

    const allNameInputs = screen.getAllByPlaceholderText(/item name/i);
    const newNameInput = allNameInputs[allNameInputs.length - 1];
    await user.type(newNameInput, "Greek Yogurt");
    expect(screen.getByDisplayValue("Greek Yogurt")).toBeInTheDocument();
  });

  it("submits the reviewed items to api.commitReceipt and calls onCommitted and onClose", async () => {
    const user = userEvent.setup();
    vi.mocked(api.commitReceipt).mockResolvedValueOnce(mockResponse);

    const onCommitted = vi.fn();
    const onClose = vi.fn();

    render(
      <ReceiptReviewModal
        data={sampleData}
        onClose={onClose}
        onCommitted={onCommitted}
      />
    );

    const submitBtn = screen.getByRole("button", {
      name: /Add Everything to Kitchen/i,
    });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(api.commitReceipt).toHaveBeenCalledWith({
        date: "2026-10-30",
        currency: "USD",
        record_spend: true,
        total_spend: 15.48,
        items: [
          {
            name: "Organic Bananas",
            category: "Produce",
            location: "pantry",
            quantity: 2,
            unit: "bunch",
            price: 3.98,
            include_inventory: true,
            include_price: true,
          },
          {
            name: "Almond Milk",
            category: "Dairy",
            location: "fridge",
            quantity: 1,
            unit: "carton",
            price: 2.99,
            include_inventory: true,
            include_price: true,
          },
        ],
      });
      expect(onCommitted).toHaveBeenCalledWith(mockResponse);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("handles commit error and calls onError", async () => {
    const user = userEvent.setup();
    vi.mocked(api.commitReceipt).mockRejectedValueOnce(
      new Error("Network connection error")
    );

    const onError = vi.fn();
    const onCommitted = vi.fn();
    const onClose = vi.fn();

    render(
      <ReceiptReviewModal
        data={sampleData}
        onClose={onClose}
        onCommitted={onCommitted}
        onError={onError}
      />
    );

    const submitBtn = screen.getByRole("button", {
      name: /Add Everything to Kitchen/i,
    });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith("Network connection error");
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Network connection error"
      );
      expect(onCommitted).not.toHaveBeenCalled();
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  it("handles modal dismiss via close button, backdrop click, or Escape key", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    const { rerender } = render(
      <ReceiptReviewModal
        data={sampleData}
        onClose={onClose}
        onCommitted={vi.fn()}
      />
    );

    // Close button
    const closeBtn = screen.getByRole("button", { name: /close modal/i });
    await user.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);

    // Backdrop click
    const backdrop = document.querySelector(".modal-backdrop") as HTMLElement;
    expect(backdrop).toBeInTheDocument();
    await user.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(2);

    // Escape key
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("defaults record_spend to false when total is 0", () => {
    const zeroData: ReceiptParsedData = {
      store: "Local Market",
      date: "2026-10-30",
      total: 0,
      currency: "USD",
      items: [],
    };

    render(
      <ReceiptReviewModal
        data={zeroData}
        onClose={vi.fn()}
        onCommitted={vi.fn()}
      />
    );

    const budgetCheckbox = screen.getByLabelText(/log spend to weekly budget/i);
    expect(budgetCheckbox).not.toBeChecked();
  });
});
