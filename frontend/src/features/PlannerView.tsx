import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { PlanEntry, Recipe, Settings } from "../types";
import { getMonday, addDays, getWeekDates } from "../utils/date";

interface PlannerViewProps {
  weekStart: string;
  setWeekStart: (w: string) => void;
  settings: Settings | null;
  recipes: Recipe[];
  onError: (msg: string) => void;
}

export const PlannerView: React.FC<PlannerViewProps> = ({
  weekStart,
  setWeekStart,
  settings,
  recipes,
  onError,
}) => {
  const [entries, setEntries] = useState<PlanEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [addingDay, setAddingDay] = useState<string | null>(null);
  const [selectedRecipeId, setSelectedRecipeId] = useState<number | "">("");
  const [slot, setSlot] = useState<string>("dinner");
  const [servingsOverride, setServingsOverride] = useState<string>("");

  const loadPlan = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getPlan(weekStart);
      setEntries(data);
    } catch (err: any) {
      onError(err.message || "Failed to load meal plan");
    } finally {
      setLoading(false);
    }
  }, [weekStart, onError]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  const handlePrevWeek = () => {
    setWeekStart(addDays(weekStart, -7));
  };

  const handleNextWeek = () => {
    setWeekStart(addDays(weekStart, 7));
  };

  const handleThisWeek = () => {
    setWeekStart(getMonday(new Date()));
  };

  const handleAutoPopulate = async () => {
    try {
      await api.autoPopulate(weekStart);
      await loadPlan();
    } catch (err: any) {
      onError(err.message || "Failed to auto-populate week");
    }
  };

  const handleMarkCooked = async (entryId: number) => {
    try {
      await api.markCooked(entryId);
      await loadPlan();
    } catch (err: any) {
      onError(err.message || "Failed to mark meal as cooked");
    }
  };

  const handleDeleteEntry = async (entryId: number) => {
    try {
      await api.deletePlanEntry(entryId);
      await loadPlan();
    } catch (err: any) {
      onError(err.message || "Failed to delete plan entry");
    }
  };

  const handleAddMeal = async (date: string) => {
    if (!selectedRecipeId) return;
    try {
      await api.addPlanEntry({
        recipe_id: Number(selectedRecipeId),
        date,
        slot: slot || null,
        servings_override: servingsOverride ? Number(servingsOverride) : null,
      });
      setAddingDay(null);
      setSelectedRecipeId("");
      setServingsOverride("");
      await loadPlan();
    } catch (err: any) {
      onError(err.message || "Failed to add meal to plan");
    }
  };

  const mealsTarget = settings?.meals_per_week ?? 5;
  const plannedCount = entries.length;
  const weekDays = getWeekDates(weekStart);

  return (
    <div className="planner-view">
      <header className="planner-header">
        <div className="week-nav">
          <button type="button" onClick={handlePrevWeek} className="btn-secondary">
            ← Prev Week
          </button>
          <button type="button" onClick={handleThisWeek} className="btn-secondary">
            This Week
          </button>
          <button type="button" onClick={handleNextWeek} className="btn-secondary">
            Next Week →
          </button>
          <span className="current-week-label">Week of {weekStart}</span>
        </div>

        <div className="planner-actions">
          <div className="progress-badge">
            <strong>
              {plannedCount} / {mealsTarget} meals planned
            </strong>
          </div>
          <button
            type="button"
            onClick={handleAutoPopulate}
            className="btn-primary"
          >
            Auto-Populate Week
          </button>
        </div>
      </header>

      {loading && <div className="loading-indicator">Loading plan...</div>}

      <div className="week-grid">
        {weekDays.map((day) => {
          const dayEntries = entries.filter((e) => e.date === day.date);
          const isAdding = addingDay === day.date;

          return (
            <div key={day.date} className="day-column">
              <div className="day-header">
                <h3>{day.dayName}</h3>
                <span className="day-sub">{day.formatted}</span>
              </div>

              <div className="day-entries">
                {dayEntries.map((entry) => {
                  const isCooked = Boolean(entry.cooked);
                  return (
                    <div
                      key={entry.id}
                      className={`plan-card ${isCooked ? "cooked" : "planned"}`}
                    >
                      <div className="card-top">
                        <span className="recipe-title">
                          {entry.title || entry.recipe_title || "Recipe"}
                        </span>
                        {isCooked ? (
                          <span className="badge badge-cooked">Cooked</span>
                        ) : (
                          <span className="badge badge-planned">Planned</span>
                        )}
                      </div>

                      <div className="card-details">
                        {entry.slot && (
                          <span className="entry-slot">{entry.slot}</span>
                        )}
                        {entry.servings_override && (
                          <span className="entry-servings">
                            {entry.servings_override} serv
                          </span>
                        )}
                      </div>

                      <div className="card-actions">
                        {!isCooked && (
                          <button
                            type="button"
                            onClick={() => handleMarkCooked(entry.id)}
                            className="btn-sm btn-success"
                          >
                            Mark Cooked
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDeleteEntry(entry.id)}
                          className="btn-sm btn-danger"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  );
                })}

                {dayEntries.length === 0 && !isAdding && (
                  <div className="empty-day">No meals planned</div>
                )}
              </div>

              {isAdding ? (
                <div className="add-meal-form">
                  <select
                    value={selectedRecipeId}
                    onChange={(e) =>
                      setSelectedRecipeId(
                        e.target.value ? Number(e.target.value) : ""
                      )
                    }
                    className="select-input"
                  >
                    <option value="">Select Recipe...</option>
                    {recipes.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title}
                      </option>
                    ))}
                  </select>

                  <div className="form-row">
                    <select
                      value={slot}
                      onChange={(e) => setSlot(e.target.value)}
                      className="select-input"
                    >
                      <option value="dinner">Dinner</option>
                      <option value="lunch">Lunch</option>
                      <option value="breakfast">Breakfast</option>
                    </select>

                    <input
                      type="number"
                      placeholder="Servings"
                      value={servingsOverride}
                      onChange={(e) => setServingsOverride(e.target.value)}
                      min="1"
                      className="number-input"
                    />
                  </div>

                  <div className="form-actions">
                    <button
                      type="button"
                      disabled={!selectedRecipeId}
                      onClick={() => handleAddMeal(day.date)}
                      className="btn-sm btn-primary"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setAddingDay(null)}
                      className="btn-sm btn-secondary"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setAddingDay(day.date);
                    if (recipes.length > 0 && !selectedRecipeId) {
                      setSelectedRecipeId(recipes[0].id);
                    }
                  }}
                  className="btn-add-meal"
                >
                  + Add Meal
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
