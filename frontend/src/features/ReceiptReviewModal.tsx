import React, { useState, useEffect } from "react";
import type {
  ReceiptParsedData,
  ReceiptCommitPayload,
  ReceiptCommitResponse,
} from "../types";
import { api } from "../api/client";

export interface ReceiptReviewModalProps {
  data: ReceiptParsedData;
  onClose: () => void;
  onCommitted: (res: ReceiptCommitResponse) => void;
  onError?: (err: string | null) => void;
}

export interface EditableReceiptRow {
  id: string;
  name: string;
  category?: string | null;
  location: "pantry" | "fridge" | "freezer";
  quantity: number;
  unit: string;
  price: number;
  include: boolean;
}

export const ReceiptReviewModal: React.FC<ReceiptReviewModalProps> = ({
  data,
  onClose,
  onCommitted,
  onError,
}) => {
  const [store, setStore] = useState(data.store || "");
  const [date, setDate] = useState(
    data.date || new Date().toISOString().split("T")[0]
  );
  const [total, setTotal] = useState<number>(data.total ?? 0);
  const [currency, setCurrency] = useState(data.currency || "USD");
  const [recordSpend, setRecordSpend] = useState((data.total ?? 0) > 0);
  const [items, setItems] = useState<EditableReceiptRow[]>(() =>
    (data.items || []).map((item, idx) => ({
      id: `item-${idx}-${Date.now()}-${Math.random()}`,
      name: item.name || item.raw_name || "",
      category: item.category ?? null,
      location: (["pantry", "fridge", "freezer"].includes(
        item.suggested_location as string
      )
        ? item.suggested_location
        : "pantry") as "pantry" | "fridge" | "freezer",
      quantity: item.quantity ?? 1,
      unit: item.unit || "",
      price: item.price ?? 0,
      include: item.include !== false,
    }))
  );

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setStore(data.store || "");
    setDate(data.date || new Date().toISOString().split("T")[0]);
    setTotal(data.total ?? 0);
    setCurrency(data.currency || "USD");
    setRecordSpend((data.total ?? 0) > 0);
    setItems(
      (data.items || []).map((item, idx) => ({
        id: `item-${idx}-${Date.now()}-${Math.random()}`,
        name: item.name || item.raw_name || "",
        category: item.category ?? null,
        location: (["pantry", "fridge", "freezer"].includes(
          item.suggested_location as string
        )
          ? item.suggested_location
          : "pantry") as "pantry" | "fridge" | "freezer",
        quantity: item.quantity ?? 1,
        unit: item.unit || "",
        price: item.price ?? 0,
        include: item.include !== false,
      }))
    );
  }, [data]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleAddItem = () => {
    setItems((prev) => [
      ...prev,
      {
        id: `item-new-${Date.now()}-${Math.random()}`,
        name: "",
        category: null,
        location: "pantry",
        quantity: 1,
        unit: "",
        price: 0,
        include: true,
      },
    ]);
  };

  const handleRemoveItem = (index: number) => {
    setItems((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleRowChange = <K extends keyof EditableReceiptRow>(
    index: number,
    field: K,
    value: EditableReceiptRow[K]
  ) => {
    setItems((prev) =>
      prev.map((row, idx) => (idx === index ? { ...row, [field]: value } : row))
    );
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    onError?.(null);

    try {
      const payload: ReceiptCommitPayload = {
        date: date || new Date().toISOString().split("T")[0],
        currency: currency || "USD",
        record_spend: recordSpend,
        total_spend: Number(total) || 0,
        items: items.map((it) => ({
          name: it.name.trim(),
          category: it.category || null,
          location: it.location,
          quantity: Number(it.quantity) || 0,
          unit: it.unit ? it.unit.trim() : "",
          price: Number(it.price) || 0,
          include_inventory: Boolean(it.include),
          include_price: Boolean(it.include),
        })),
      };

      const res = await api.commitReceipt(payload);
      onCommitted(res);
      onClose();
    } catch (err: any) {
      const msg = err?.message || "Failed to commit receipt";
      setErrorMessage(msg);
      onError?.(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <dialog
      open
      className="modal-dialog receipt-modal-dialog"
      aria-modal="true"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          onClose();
        }
      }}
    >
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-content receipt-modal-content">
        <header className="modal-header">
          <div>
            <h2>Review Ingested Receipt</h2>
            <p className="modal-subtitle">
              Verify extracted items, destinations, and prices before saving to your kitchen.
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            ×
          </button>
        </header>

        <div className="modal-body receipt-modal-body">
          {errorMessage && (
            <div className="review-notes-alert review-error-alert" role="alert">
              <span className="alert-badge">Error</span>
              <span className="alert-message">{errorMessage}</span>
            </div>
          )}

          {/* Receipt Header Information */}
          <section className="receipt-header-section">
            <div className="receipt-header-grid">
              <div className="form-group">
                <label htmlFor="receipt-store">Store Name</label>
                <input
                  id="receipt-store"
                  className="text-input"
                  type="text"
                  placeholder="e.g. Trader Joe's, Costco"
                  aria-label="Store Name"
                  value={store}
                  onChange={(e) => setStore(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label htmlFor="receipt-date">Receipt Date</label>
                <input
                  id="receipt-date"
                  className="text-input"
                  type="date"
                  aria-label="Receipt Date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label htmlFor="receipt-total">Total Spend</label>
                <div className="currency-input-group">
                  <input
                    id="receipt-total"
                    className="number-input receipt-total-input"
                    type="number"
                    step="0.01"
                    min="0"
                    aria-label="Total Spend"
                    value={total}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setTotal(isNaN(val) ? 0 : val);
                    }}
                  />
                  <input
                    id="receipt-currency"
                    className="text-input receipt-currency-input"
                    type="text"
                    maxLength={5}
                    aria-label="Currency"
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  />
                </div>
              </div>

              <div className="form-group checkbox-form-group">
                <label className="checkbox-label" htmlFor="receipt-record-spend">
                  <input
                    id="receipt-record-spend"
                    type="checkbox"
                    checked={recordSpend}
                    onChange={(e) => setRecordSpend(e.target.checked)}
                  />
                  <span>Log spend to weekly budget</span>
                </label>
              </div>
            </div>
          </section>

          {/* Items Section */}
          <section className="receipt-items-section">
            <div className="section-header">
              <h3>Receipt Items ({items.length})</h3>
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={handleAddItem}
              >
                + Add Line Item
              </button>
            </div>

            <div className="receipt-table-container">
              <table className="receipt-table">
                <thead>
                  <tr>
                    <th className="th-include" scope="col">Include</th>
                    <th className="th-item" scope="col">Item Name</th>
                    <th className="th-location" scope="col">Location</th>
                    <th className="th-qty" scope="col">Qty</th>
                    <th className="th-unit" scope="col">Unit</th>
                    <th className="th-price" scope="col">Price</th>
                    <th className="th-actions" scope="col"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row, idx) => (
                    <tr
                      key={row.id}
                      className={`receipt-row ${!row.include ? "receipt-row-excluded" : ""}`}
                    >
                      <td className="td-include">
                        <input
                          type="checkbox"
                          aria-label={`Include ${row.name || "item"}`}
                          checked={row.include}
                          onChange={(e) =>
                            handleRowChange(idx, "include", e.target.checked)
                          }
                        />
                      </td>
                      <td className="td-item">
                        <input
                          type="text"
                          className="text-input receipt-input-name"
                          aria-label="Item name"
                          placeholder="Item name"
                          value={row.name}
                          onChange={(e) =>
                            handleRowChange(idx, "name", e.target.value)
                          }
                        />
                      </td>
                      <td className="td-location">
                        <select
                          className="select-input receipt-select-location"
                          aria-label="Location"
                          value={row.location}
                          onChange={(e) =>
                            handleRowChange(
                              idx,
                              "location",
                              e.target.value as "pantry" | "fridge" | "freezer"
                            )
                          }
                        >
                          <option value="pantry">Pantry</option>
                          <option value="fridge">Fridge</option>
                          <option value="freezer">Freezer</option>
                        </select>
                      </td>
                      <td className="td-qty">
                        <input
                          type="number"
                          step="any"
                          min="0"
                          className="number-input receipt-input-qty"
                          aria-label="Quantity"
                          value={row.quantity}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            handleRowChange(idx, "quantity", isNaN(val) ? 0 : val);
                          }}
                        />
                      </td>
                      <td className="td-unit">
                        <input
                          type="text"
                          className="text-input receipt-input-unit"
                          aria-label="Unit"
                          placeholder="unit"
                          value={row.unit}
                          onChange={(e) =>
                            handleRowChange(idx, "unit", e.target.value)
                          }
                        />
                      </td>
                      <td className="td-price">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          className="number-input receipt-input-price"
                          aria-label="Price"
                          value={row.price}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            handleRowChange(idx, "price", isNaN(val) ? 0 : val);
                          }}
                        />
                      </td>
                      <td className="td-actions">
                        <button
                          type="button"
                          className="btn-danger-icon"
                          aria-label={`Remove item ${row.name || idx + 1}`}
                          onClick={() => handleRemoveItem(idx)}
                          title="Remove item"
                        >
                          ×
                        </button>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && (
                    <tr>
                      <td colSpan={7} className="receipt-empty-state">
                        No items found on receipt. Click "+ Add Line Item" to add manually.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="receipt-items-footer">
              <span className="receipt-items-count">
                {items.filter((i) => i.include).length} of {items.length} items selected to add
              </span>
            </div>
          </section>
        </div>

        <footer className="modal-footer">
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? "Adding to kitchen..." : "Add Everything to Kitchen"}
          </button>
        </footer>
      </div>
    </dialog>
  );
};
