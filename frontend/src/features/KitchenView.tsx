import React, { useState, useEffect, useCallback, useRef } from "react";
import type {
  InventoryItem,
  ReceiptParsedData,
  ReceiptCommitResponse,
} from "../types";
import { api } from "../api/client";
import { ReceiptReviewModal } from "./ReceiptReviewModal";

interface KitchenViewProps {
  onError?: (msg: string | null) => void;
}

export const KitchenView: React.FC<KitchenViewProps> = ({ onError }) => {
  const [activeLocation, setActiveLocation] = useState<"pantry" | "fridge" | "freezer">("pantry");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Receipt Ingestion state
  const [isParsing, setIsParsing] = useState(false);
  const [parsedReceipt, setParsedReceipt] = useState<ReceiptParsedData | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  // Quick-add form
  const [addName, setAddName] = useState("");
  const [addCategory, setAddCategory] = useState("");
  const [addQuantity, setAddQuantity] = useState<number | string>(1);
  const [addUnit, setAddUnit] = useState("");
  const [addLocation, setAddLocation] = useState<string>("pantry");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Sync addLocation with activeLocation when tab changes
  useEffect(() => {
    setAddLocation(activeLocation);
  }, [activeLocation]);

  const loadInventory = useCallback(
    async (location: string) => {
      setIsLoading(true);
      try {
        const data = await api.getInventory(location);
        setItems(data);
      } catch (err: any) {
        onError?.(err.message || "Failed to load inventory");
      } finally {
        setIsLoading(false);
      }
    },
    [onError]
  );

  useEffect(() => {
    loadInventory(activeLocation);
  }, [activeLocation, loadInventory]);

  const processFile = async (file: File) => {
    setIsParsing(true);
    setToastMessage(null);
    try {
      const parsed = await api.parseReceipt(file);
      setParsedReceipt(parsed);
    } catch (err: any) {
      const msg = err?.message || "Failed to parse receipt";
      onError?.(msg);
    } finally {
      setIsParsing(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await processFile(files[0]);
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await processFile(file);
    }
  };

  const handleReceiptCommitted = async (res: ReceiptCommitResponse) => {
    await loadInventory(activeLocation);
    const spendFormatted = Number(res.spend_recorded || 0).toFixed(2);
    setToastMessage(
      `Receipt processed: added ${res.inventory_items_added} items, updated ${res.prices_updated} prices, recorded $${spendFormatted} spend`
    );
    setParsedReceipt(null);
  };

  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addName.trim()) {
      onError?.("Item name is required");
      return;
    }

    setIsSubmitting(true);
    try {
      if (addCategory.trim()) {
        await api.createItem({
          name: addName.trim(),
          category: addCategory.trim(),
        });
      }

      await api.addInventory({
        name: addName.trim(),
        location: addLocation,
        quantity: Number(addQuantity) || 1,
        unit: addUnit.trim() || undefined,
      });

      setAddName("");
      setAddCategory("");
      setAddQuantity(1);
      setAddUnit("");

      await loadInventory(activeLocation);
    } catch (err: any) {
      onError?.(err.message || "Failed to add inventory item");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStepQuantity = async (item: InventoryItem, delta: number) => {
    try {
      await api.patchInventory(item.id, delta);
      await loadInventory(activeLocation);
    } catch (err: any) {
      onError?.(err.message || "Failed to update item quantity");
    }
  };

  const handleDeleteItem = async (item: InventoryItem) => {
    try {
      await api.deleteInventory(item.id);
      await loadInventory(activeLocation);
    } catch (err: any) {
      onError?.(err.message || "Failed to delete item");
    }
  };

  const filteredItems = items.filter((item) =>
    item.item_name.toLowerCase().includes(searchQuery.toLowerCase().trim())
  );

  return (
    <div
      className={`kitchen-view ${isDragging ? "drop-active" : ""}`}
      data-testid="kitchen-view"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag & Drop Visual Overlay */}
      {isDragging && (
        <div className="receipt-drop-overlay">
          <div className="receipt-drop-message">
            <span className="drop-icon">📄</span>
            <span>Drop receipt image or PDF here</span>
          </div>
        </div>
      )}

      {/* Success / Status Toast Banner */}
      {toastMessage && (
        <div className="receipt-toast-banner" role="status">
          <span>{toastMessage}</span>
          <button
            type="button"
            className="receipt-toast-dismiss"
            onClick={() => setToastMessage(null)}
            aria-label="Dismiss message"
          >
            ×
          </button>
        </div>
      )}

      {/* Parsing in progress indicator */}
      {isParsing && (
        <div className="receipt-parsing-bar" role="status">
          <span className="spinner-sm" aria-hidden="true" />
          <span>Parsing receipt...</span>
        </div>
      )}

      {/* Location Navigation, Ingest Receipt Button & Search Toolbar */}
      <div className="kitchen-toolbar">
        <div className="kitchen-toolbar-left">
          <div className="tab-pill-group">
            <button
              type="button"
              className={`tab-pill ${activeLocation === "pantry" ? "active" : ""}`}
              onClick={() => setActiveLocation("pantry")}
            >
              Pantry
            </button>
            <button
              type="button"
              className={`tab-pill ${activeLocation === "fridge" ? "active" : ""}`}
              onClick={() => setActiveLocation("fridge")}
            >
              Fridge
            </button>
            <button
              type="button"
              className={`tab-pill ${activeLocation === "freezer" ? "active" : ""}`}
              onClick={() => setActiveLocation("freezer")}
            >
              Freezer
            </button>
          </div>

          <button
            type="button"
            className="btn-secondary ingest-receipt-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isParsing}
            title="Upload or snap a grocery receipt to populate inventory"
          >
            📷 Ingest Receipt
          </button>

          <input
            type="file"
            ref={fileInputRef}
            className="sr-only receipt-file-input"
            accept="image/*,application/pdf"
            capture="environment"
            onChange={handleFileChange}
            aria-label="Upload receipt image or PDF"
          />
        </div>

        <div className="search-bar">
          <input
            type="text"
            className="text-input"
            placeholder="Search inventory..."
            aria-label="Search inventory"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Quick Add Form */}
      <section className="kitchen-add-card">
        <h3>Add to Kitchen</h3>
        <form onSubmit={handleQuickAdd} className="kitchen-add-form">
          <div className="add-form-grid">
            <input
              type="text"
              className="text-input"
              placeholder="Item name (e.g. Eggs, Rice)"
              aria-label="Item name"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              required
            />
            <input
              type="text"
              className="text-input"
              placeholder="Category (e.g. dairy, produce)"
              aria-label="Category"
              value={addCategory}
              onChange={(e) => setAddCategory(e.target.value)}
            />
            <div className="qty-unit-row">
              <input
                type="number"
                className="number-input input-qty"
                placeholder="Qty"
                step="any"
                min="0"
                aria-label="Quantity"
                value={addQuantity}
                onChange={(e) => setAddQuantity(e.target.value)}
                required
              />
              <input
                type="text"
                className="text-input input-unit"
                placeholder="Unit (e.g. carton, kg)"
                aria-label="Unit"
                value={addUnit}
                onChange={(e) => setAddUnit(e.target.value)}
              />
            </div>
            <select
              className="select-input"
              aria-label="Location"
              value={addLocation}
              onChange={(e) => setAddLocation(e.target.value)}
            >
              <option value="pantry">Pantry</option>
              <option value="fridge">Fridge</option>
              <option value="freezer">Freezer</option>
            </select>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting || !addName.trim()}
            >
              {isSubmitting ? "Adding..." : "Add Item"}
            </button>
          </div>
        </form>
      </section>

      {/* Inventory Table / Items List */}
      <div className="kitchen-table-container">
        {isLoading ? (
          <div className="loading-indicator">Loading inventory...</div>
        ) : filteredItems.length === 0 ? (
          <div className="empty-state">
            {searchQuery
              ? `No items matching "${searchQuery}" in ${activeLocation}.`
              : `Your ${activeLocation} is currently empty. Add items using the form above.`}
          </div>
        ) : (
          <table className="kitchen-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Quantity</th>
                <th>Adjust</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.id} className="inventory-row">
                  <td className="item-name-cell">
                    <strong>{item.item_name}</strong>
                  </td>
                  <td className="item-qty-cell">
                    {item.quantity} {item.unit || ""}
                  </td>
                  <td className="item-stepper-cell">
                    <div className="stepper-group">
                      <button
                        type="button"
                        className="stepper-btn"
                        onClick={() => handleStepQuantity(item, -1)}
                        aria-label={`Decrease ${item.item_name}`}
                      >
                        −
                      </button>
                      <button
                        type="button"
                        className="stepper-btn"
                        onClick={() => handleStepQuantity(item, 1)}
                        aria-label={`Increase ${item.item_name}`}
                      >
                        +
                      </button>
                    </div>
                  </td>
                  <td className="item-action-cell">
                    <button
                      type="button"
                      className="btn-danger btn-sm"
                      onClick={() => handleDeleteItem(item)}
                      aria-label={`Delete ${item.item_name}`}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Receipt Review Modal */}
      {parsedReceipt && (
        <ReceiptReviewModal
          data={parsedReceipt}
          onClose={() => setParsedReceipt(null)}
          onCommitted={handleReceiptCommitted}
          onError={onError}
        />
      )}
    </div>
  );
};
