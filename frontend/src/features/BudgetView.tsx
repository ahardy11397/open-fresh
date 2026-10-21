import React, { useState, useEffect, useCallback } from "react";
import type { BudgetSummary, Item } from "../types";
import { api } from "../api/client";

interface BudgetViewProps {
  weekStart: string;
  onError?: (msg: string | null) => void;
}

export const BudgetView: React.FC<BudgetViewProps> = ({ weekStart, onError }) => {
  const [budget, setBudget] = useState<BudgetSummary | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Set Budget Form state
  const [targetInput, setTargetInput] = useState<number | string>(100);
  const [targetCurrency, setTargetCurrency] = useState("USD");
  const [isSettingBudget, setIsSettingBudget] = useState(false);

  // Log Spend Form state
  const [spendAmount, setSpendAmount] = useState<number | string>("");
  const [spendCurrency, setSpendCurrency] = useState("USD");
  const [spendDate, setSpendDate] = useState(weekStart);
  const [spendSource, setSpendSource] = useState("");
  const [isLoggingSpend, setIsLoggingSpend] = useState(false);
  const [spendSuccessMsg, setSpendSuccessMsg] = useState<string | null>(null);

  // Price Library Form: Record Own Price
  const [ownItemId, setOwnItemId] = useState<number | string>("");
  const [ownPrice, setOwnPrice] = useState<number | string>("");
  const [ownCurrency, setOwnCurrency] = useState("USD");
  const [ownDate, setOwnDate] = useState(weekStart);
  const [ownPkgQty, setOwnPkgQty] = useState<number | string>("");
  const [ownPkgUnit, setOwnPkgUnit] = useState("");
  const [isSavingOwnPrice, setIsSavingOwnPrice] = useState(false);
  const [ownPriceSuccessMsg, setOwnPriceSuccessMsg] = useState<string | null>(null);

  // Price Library Form: Set Estimate
  const [estimateItemId, setEstimateItemId] = useState<number | string>("");
  const [estimateCategory, setEstimateCategory] = useState("");
  const [estimatePrice, setEstimatePrice] = useState<number | string>("");
  const [estimateCurrency, setEstimateCurrency] = useState("USD");
  const [estimatePkgQty, setEstimatePkgQty] = useState<number | string>("");
  const [estimatePkgUnit, setEstimatePkgUnit] = useState("");
  const [isSavingEstimate, setIsSavingEstimate] = useState(false);
  const [estimateSuccessMsg, setEstimateSuccessMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [budgetData, itemsData] = await Promise.all([
        api.getBudget(weekStart).catch(() => null),
        api.getItems().catch(() => []),
      ]);

      if (budgetData) {
        setBudget(budgetData);
        setTargetInput(budgetData.target);
        if (budgetData.currency) {
          setTargetCurrency(budgetData.currency);
          setSpendCurrency(budgetData.currency);
          setOwnCurrency(budgetData.currency);
          setEstimateCurrency(budgetData.currency);
        }
      }
      setItems(itemsData);
      if (itemsData.length > 0 && !ownItemId) {
        setOwnItemId(itemsData[0].id);
      }
    } catch (err: any) {
      onError?.(err.message || "Failed to load budget data");
    } finally {
      setIsLoading(false);
    }
  }, [weekStart, onError]);

  useEffect(() => {
    loadData();
    setSpendDate(weekStart);
    setOwnDate(weekStart);
  }, [weekStart, loadData]);

  const formatMoney = (val?: number | null, curr = "USD") => {
    const num = val ?? 0;
    const symbol = curr === "USD" ? "$" : curr + " ";
    return `${symbol}${num.toFixed(2)}`;
  };

  const handleSetBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSettingBudget(true);
    try {
      await api.putBudget(weekStart, {
        target: Number(targetInput) || 0,
        currency: targetCurrency,
      });
      await loadData();
    } catch (err: any) {
      onError?.(err.message || "Failed to update weekly budget");
    } finally {
      setIsSettingBudget(false);
    }
  };

  const handleLogSpend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!spendAmount) return;
    setIsLoggingSpend(true);
    setSpendSuccessMsg(null);
    try {
      await api.postSpend(
        {
          price: Number(spendAmount),
          currency: spendCurrency,
          date: spendDate,
          source: spendSource.trim() || undefined,
        },
        weekStart
      );
      setSpendAmount("");
      setSpendSource("");
      setSpendSuccessMsg("Spend logged successfully!");
      await loadData();
      setTimeout(() => setSpendSuccessMsg(null), 3000);
    } catch (err: any) {
      onError?.(err.message || "Failed to log spend");
    } finally {
      setIsLoggingSpend(false);
    }
  };

  const handleRecordOwnPrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ownItemId || !ownPrice) return;
    setIsSavingOwnPrice(true);
    setOwnPriceSuccessMsg(null);
    try {
      await api.postOwnPrice({
        item_id: Number(ownItemId),
        price: Number(ownPrice),
        currency: ownCurrency,
        date: ownDate,
        package_quantity: ownPkgQty ? Number(ownPkgQty) : undefined,
        package_unit: ownPkgUnit.trim() || undefined,
      });
      setOwnPrice("");
      setOwnPkgQty("");
      setOwnPkgUnit("");
      setOwnPriceSuccessMsg("Price recorded!");
      setTimeout(() => setOwnPriceSuccessMsg(null), 3000);
    } catch (err: any) {
      onError?.(err.message || "Failed to record price");
    } finally {
      setIsSavingOwnPrice(false);
    }
  };

  const handleSetEstimate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!estimatePrice) return;
    setIsSavingEstimate(true);
    setEstimateSuccessMsg(null);
    try {
      await api.postEstimate({
        item_id: estimateItemId ? Number(estimateItemId) : undefined,
        category: estimateCategory.trim() || undefined,
        price: Number(estimatePrice),
        currency: estimateCurrency,
        package_quantity: estimatePkgQty ? Number(estimatePkgQty) : undefined,
        package_unit: estimatePkgUnit.trim() || undefined,
      });
      setEstimatePrice("");
      setEstimatePkgQty("");
      setEstimatePkgUnit("");
      setEstimateSuccessMsg("Estimate saved!");
      setTimeout(() => setEstimateSuccessMsg(null), 3000);
    } catch (err: any) {
      onError?.(err.message || "Failed to save estimate");
    } finally {
      setIsSavingEstimate(false);
    }
  };

  const currency = budget?.currency || "USD";
  const target = budget?.target ?? 0;
  const estimated = budget?.estimated ?? budget?.list_estimated_cost ?? 0;
  const actual = budget?.actual ?? budget?.actual_spend ?? 0;
  const remaining = budget?.remaining ?? (target - actual);

  return (
    <div className="budget-view">
      <header className="budget-header">
        <div>
          <h2>Weekly Budget & Prices</h2>
          <span className="week-label">Week of {weekStart}</span>
        </div>
      </header>

      {/* Summary Cards */}
      <div className="budget-cards-grid">
        <div className="budget-card">
          <span className="card-label">Weekly Target</span>
          <span className="card-value target-val">{formatMoney(target, currency)}</span>
        </div>
        <div className="budget-card">
          <span className="card-label">Estimated List Cost</span>
          <span className="card-value estimated-val">
            {formatMoney(estimated, currency)}
          </span>
        </div>
        <div className="budget-card">
          <span className="card-label">Actual Spend</span>
          <span className="card-value spend-val">{formatMoney(actual, currency)}</span>
        </div>
        <div className={`budget-card ${remaining < 0 ? "card-over-budget" : ""}`}>
          <span className="card-label">Remaining</span>
          <span className="card-value remaining-val">
            {formatMoney(remaining, currency)}
          </span>
        </div>
      </div>

      <div className="budget-forms-grid">
        {/* Set Budget Form */}
        <section className="budget-section-card">
          <h3>Set Weekly Budget</h3>
          <form onSubmit={handleSetBudget} className="budget-form">
            <div className="form-group">
              <label htmlFor="budget-target">Weekly Target</label>
              <div className="input-group">
                <input
                  id="budget-target"
                  type="number"
                  step="any"
                  min="0"
                  className="number-input"
                  aria-label="Weekly Target"
                  value={targetInput}
                  onChange={(e) => setTargetInput(e.target.value)}
                  required
                />
                <select
                  className="select-input select-currency"
                  aria-label="Target Currency"
                  value={targetCurrency}
                  onChange={(e) => setTargetCurrency(e.target.value)}
                >
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                  <option value="CAD">CAD ($)</option>
                </select>
              </div>
            </div>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSettingBudget}
            >
              {isSettingBudget ? "Saving..." : "Set Budget"}
            </button>
          </form>
        </section>

        {/* Log Spend Form */}
        <section className="budget-section-card">
          <h3>Log Grocery Spend</h3>
          <form onSubmit={handleLogSpend} className="budget-form">
            <div className="form-row">
              <div className="form-group flex-1">
                <label htmlFor="spend-amount">Spend Amount</label>
                <input
                  id="spend-amount"
                  type="number"
                  step="any"
                  min="0.01"
                  className="number-input"
                  placeholder="0.00"
                  aria-label="Spend amount"
                  value={spendAmount}
                  onChange={(e) => setSpendAmount(e.target.value)}
                  required
                />
              </div>
              <div className="form-group flex-1">
                <label htmlFor="spend-date">Date</label>
                <input
                  id="spend-date"
                  type="date"
                  className="text-input"
                  aria-label="Spend date"
                  value={spendDate}
                  onChange={(e) => setSpendDate(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="spend-source">Source / Store (Optional)</label>
              <input
                id="spend-source"
                type="text"
                className="text-input"
                placeholder="e.g. Trader Joe's, Safeway receipt"
                aria-label="Spend source"
                value={spendSource}
                onChange={(e) => setSpendSource(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="btn-primary"
              disabled={isLoggingSpend || !spendAmount}
            >
              {isLoggingSpend ? "Logging..." : "Log Spend"}
            </button>
            {spendSuccessMsg && (
              <span className="success-inline">{spendSuccessMsg}</span>
            )}
          </form>
        </section>
      </div>

      {/* Price Library Manager */}
      <section className="price-library-section">
        <h3>Price Library</h3>
        <p className="section-help-text">
          Record known prices or category fallback estimates to accurately predict grocery costs.
        </p>

        <div className="budget-forms-grid">
          {/* Record Own Price */}
          <div className="price-card">
            <h4>Record Item Price</h4>
            <form onSubmit={handleRecordOwnPrice} className="budget-form">
              <div className="form-group">
                <label htmlFor="own-item-select">Item</label>
                <select
                  id="own-item-select"
                  className="select-input"
                  aria-label="Item for own price"
                  value={ownItemId}
                  onChange={(e) => setOwnItemId(e.target.value)}
                  required
                >
                  <option value="">Select an item...</option>
                  {items.map((it) => (
                    <option key={it.id} value={it.id}>
                      {it.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label htmlFor="own-price-input">Price</label>
                  <input
                    id="own-price-input"
                    type="number"
                    step="any"
                    min="0.01"
                    className="number-input"
                    placeholder="0.00"
                    aria-label="Own price"
                    value={ownPrice}
                    onChange={(e) => setOwnPrice(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="own-date-input">Date</label>
                  <input
                    id="own-date-input"
                    type="date"
                    className="text-input"
                    aria-label="Own price date"
                    value={ownDate}
                    onChange={(e) => setOwnDate(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label htmlFor="own-pkg-qty">Package Qty (optional)</label>
                  <input
                    id="own-pkg-qty"
                    type="number"
                    step="any"
                    min="0"
                    className="number-input"
                    placeholder="e.g. 500"
                    aria-label="Package quantity"
                    value={ownPkgQty}
                    onChange={(e) => setOwnPkgQty(e.target.value)}
                  />
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="own-pkg-unit">Package Unit (optional)</label>
                  <input
                    id="own-pkg-unit"
                    type="text"
                    className="text-input"
                    placeholder="e.g. g, oz"
                    aria-label="Package unit"
                    value={ownPkgUnit}
                    onChange={(e) => setOwnPkgUnit(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="btn-secondary"
                disabled={isSavingOwnPrice || !ownItemId || !ownPrice}
              >
                {isSavingOwnPrice ? "Saving..." : "Record Own Price"}
              </button>
              {ownPriceSuccessMsg && (
                <span className="success-inline">{ownPriceSuccessMsg}</span>
              )}
            </form>
          </div>

          {/* Set Estimate */}
          <div className="price-card">
            <h4>Set Fallback Estimate</h4>
            <form onSubmit={handleSetEstimate} className="budget-form">
              <div className="form-row">
                <div className="form-group flex-1">
                  <label htmlFor="estimate-item-select">Item (Optional)</label>
                  <select
                    id="estimate-item-select"
                    className="select-input"
                    aria-label="Item for estimate"
                    value={estimateItemId}
                    onChange={(e) => setEstimateItemId(e.target.value)}
                  >
                    <option value="">Any / Category fallback</option>
                    {items.map((it) => (
                      <option key={it.id} value={it.id}>
                        {it.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="estimate-category">Category (Optional)</label>
                  <input
                    id="estimate-category"
                    type="text"
                    className="text-input"
                    placeholder="e.g. produce, dairy"
                    aria-label="Category for estimate"
                    value={estimateCategory}
                    onChange={(e) => setEstimateCategory(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label htmlFor="estimate-price-input">Estimated Price</label>
                  <input
                    id="estimate-price-input"
                    type="number"
                    step="any"
                    min="0.01"
                    className="number-input"
                    placeholder="0.00"
                    aria-label="Estimate price"
                    value={estimatePrice}
                    onChange={(e) => setEstimatePrice(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="estimate-pkg-unit">Package Unit (optional)</label>
                  <input
                    id="estimate-pkg-unit"
                    type="text"
                    className="text-input"
                    placeholder="e.g. lb, bunch"
                    aria-label="Estimate package unit"
                    value={estimatePkgUnit}
                    onChange={(e) => setEstimatePkgUnit(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="btn-secondary"
                disabled={isSavingEstimate || !estimatePrice}
              >
                {isSavingEstimate ? "Saving..." : "Set Estimate"}
              </button>
              {estimateSuccessMsg && (
                <span className="success-inline">{estimateSuccessMsg}</span>
              )}
            </form>
          </div>
        </div>
      </section>
    </div>
  );
};
