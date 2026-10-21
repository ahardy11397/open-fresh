import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { GroceryLine, BudgetSummary } from "../types";

interface GroceryListViewProps {
  weekStart: string;
  onError: (msg: string) => void;
}

export const GroceryListView: React.FC<GroceryListViewProps> = ({
  weekStart,
  onError,
}) => {
  const [lines, setLines] = useState<GroceryLine[]>([]);
  const [budget, setBudget] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({});
  const [itemLocations, setItemLocations] = useState<
    Record<number, "pantry" | "fridge" | "freezer">
  >({});
  const [itemPrices, setItemPrices] = useState<Record<number, string>>({});
  const [logSpend, setLogSpend] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [listData, budgetData] = await Promise.all([
        api.getList(weekStart),
        api.getBudget(weekStart).catch(() => null),
      ]);
      setLines(listData);
      setBudget(budgetData);
    } catch (err: any) {
      onError(err.message || "Failed to load grocery list");
    } finally {
      setLoading(false);
    }
  }, [weekStart, onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleChecked = (itemId: number) => {
    setCheckedItems((prev) => ({
      ...prev,
      [itemId]: !prev[itemId],
    }));
  };

  const handleLocationChange = (
    itemId: number,
    loc: "pantry" | "fridge" | "freezer"
  ) => {
    setItemLocations((prev) => ({
      ...prev,
      [itemId]: loc,
    }));
  };

  const handleCompleteShopping = async () => {
    const toAdd = lines.filter((line) => checkedItems[line.item_id]);
    if (toAdd.length === 0) return;

    try {
      for (const line of toAdd) {
        const location = itemLocations[line.item_id] || "pantry";
        const quantity = line.quantity ?? 1;
        const unit = line.unit || "";

        // 1. Add to inventory
        await api.addInventory({
          item_id: line.item_id,
          location,
          quantity,
          unit,
        });

        // 2. Optionally record own price and spend
        const actualPrice = itemPrices[line.item_id]
          ? parseFloat(itemPrices[line.item_id])
          : line.price;

        if (actualPrice && logSpend) {
          const currency = line.currency || line.price_currency || "USD";
          try {
            await api.postOwnPrice({
              item_id: line.item_id,
              price: actualPrice,
              currency,
              date: new Date().toISOString().slice(0, 10),
              package_quantity: quantity > 0 ? quantity : 1,
              package_unit: unit,
            });
            await api.postSpend({
              item_id: line.item_id,
              price: actualPrice,
              currency,
              date: new Date().toISOString().slice(0, 10),
              source: "grocery_shopping",
            });
          } catch {
            // Spend logging error shouldn't block the rest
          }
        }
      }

      // Clear checked items and reload
      setCheckedItems({});
      await loadData();
    } catch (err: any) {
      onError(err.message || "Failed to update inventory from shopping list");
    }
  };

  const checkedCount = Object.values(checkedItems).filter(Boolean).length;

  return (
    <div className="grocery-list-view">
      <header className="grocery-header">
        <div className="grocery-title-area">
          <h2>Grocery Shopping List</h2>
          <span className="week-label">Week of {weekStart}</span>
        </div>

        {budget && (
          <div className="budget-summary-banner">
            <span className="budget-stat">
              Target: {budget.currency} {budget.target.toFixed(2)}
            </span>
            <span className="budget-stat">
              Estimated: {budget.currency}{" "}
              {(budget.estimated ?? budget.list_estimated_cost ?? 0).toFixed(2)}
            </span>
            <span className="budget-stat">
              Remaining: {budget.currency}{" "}
              {(budget.remaining ?? 0).toFixed(2)}
            </span>
          </div>
        )}

        <div className="grocery-actions">
          <label className="checkbox-label log-spend-toggle">
            <input
              type="checkbox"
              checked={logSpend}
              onChange={(e) => setLogSpend(e.target.checked)}
            />
            Log checked items to weekly spend
          </label>

          <button
            type="button"
            disabled={checkedCount === 0}
            onClick={handleCompleteShopping}
            className="btn-primary"
          >
            Complete Shopping ({checkedCount} items)
          </button>
        </div>
      </header>

      {loading && <div className="loading-indicator">Loading grocery list...</div>}

      {lines.length === 0 && !loading ? (
        <div className="empty-state">
          All ingredients are stocked! No items needed for this week.
        </div>
      ) : (
        <div className="grocery-table-container">
          <table className="grocery-table">
            <thead>
              <tr>
                <th className="th-check">Picked</th>
                <th>Item & Quantity</th>
                <th>Est. Price</th>
                <th>Source</th>
                <th>Destination Location</th>
                <th>Price Paid</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const isChecked = Boolean(checkedItems[line.item_id]);
                const loc = itemLocations[line.item_id] || "pantry";
                const qtyText =
                  line.quantity !== null
                    ? `${line.quantity}${line.unit ? ` ${line.unit}` : ""}`
                    : line.unit || "any";

                return (
                  <tr
                    key={line.item_id}
                    className={`grocery-row ${isChecked ? "row-checked" : ""}`}
                  >
                    <td className="td-check">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleChecked(line.item_id)}
                        aria-label={`Mark ${line.name} as picked`}
                      />
                    </td>
                    <td className="td-item">
                      <span className="item-text">
                        {line.name} ({qtyText})
                      </span>
                    </td>
                    <td className="td-price">
                      {line.price !== null && line.price !== undefined ? (
                        <span>
                          {line.currency || line.price_currency || "$"}{" "}
                          {Number(line.price).toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="td-source">
                      <span
                        className={`badge badge-source badge-${line.price_source || "unpriced"}`}
                      >
                        {line.price_source || "unpriced"}
                      </span>
                    </td>
                    <td className="td-location">
                      <label className="sr-only" htmlFor={`loc-${line.item_id}`}>
                        Destination location
                      </label>
                      <select
                        id={`loc-${line.item_id}`}
                        aria-label="Destination location"
                        value={loc}
                        onChange={(e) =>
                          handleLocationChange(
                            line.item_id,
                            e.target.value as "pantry" | "fridge" | "freezer"
                          )
                        }
                        className="select-input select-sm"
                      >
                        <option value="pantry">Pantry</option>
                        <option value="fridge">Fridge</option>
                        <option value="freezer">Freezer</option>
                      </select>
                    </td>
                    <td className="td-paid">
                      <input
                        type="number"
                        step="0.01"
                        placeholder={
                          line.price !== null && line.price !== undefined
                            ? String(Number(line.price).toFixed(2))
                            : "0.00"
                        }
                        value={itemPrices[line.item_id] || ""}
                        onChange={(e) =>
                          setItemPrices({
                            ...itemPrices,
                            [line.item_id]: e.target.value,
                          })
                        }
                        className="number-input input-sm"
                        aria-label={`Actual price paid for ${line.name}`}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
