import React, { useState, useEffect } from "react";
import type { Settings } from "../types";
import { api } from "../api/client";

interface SettingsViewProps {
  settings: Settings | null;
  onRefresh?: () => Promise<void> | void;
  onError?: (msg: string | null) => void;
}

const ALL_DAYS = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
];

export const SettingsView: React.FC<SettingsViewProps> = ({
  settings: initialSettings,
  onRefresh,
  onError,
}) => {
  const [householdSize, setHouseholdSize] = useState<number | string>(2);
  const [mealsPerWeek, setMealsPerWeek] = useState<number | string>(5);
  const [preferredDays, setPreferredDays] = useState<string[]>([
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
  ]);
  const [isSaving, setIsSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (initialSettings) {
      setHouseholdSize(initialSettings.household_size);
      setMealsPerWeek(initialSettings.meals_per_week);
      if (initialSettings.preferred_days) {
        const days = initialSettings.preferred_days
          .split(",")
          .map((d) => d.trim().toLowerCase())
          .filter(Boolean);
        setPreferredDays(days);
      }
    } else {
      api
        .getSettings()
        .then((s) => {
          if (s) {
            setHouseholdSize(s.household_size);
            setMealsPerWeek(s.meals_per_week);
            if (s.preferred_days) {
              const days = s.preferred_days
                .split(",")
                .map((d) => d.trim().toLowerCase())
                .filter(Boolean);
              setPreferredDays(days);
            }
          }
        })
        .catch((err) => {
          onError?.(err.message || "Failed to load settings");
        });
    }
  }, [initialSettings, onError]);

  const toggleDay = (dayKey: string) => {
    setPreferredDays((prev) =>
      prev.includes(dayKey)
        ? prev.filter((d) => d !== dayKey)
        : [...prev, dayKey]
    );
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSuccessMessage(null);
    try {
      const daysStr = preferredDays.join(",");
      await api.putSettings({
        household_size: Number(householdSize) || 1,
        meals_per_week: Number(mealsPerWeek) || 1,
        preferred_days: daysStr,
      });

      setSuccessMessage("Settings saved successfully!");
      await onRefresh?.();
      setTimeout(() => setSuccessMessage(null), 3500);
    } catch (err: any) {
      onError?.(err.message || "Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="settings-view">
      <header className="settings-header">
        <h2>Household Settings</h2>
        <p className="settings-subtitle">
          Configure default meal planner targets, household size for recipe scaling, and cooking days.
        </p>
      </header>

      <div className="settings-card">
        <form onSubmit={handleSave} className="settings-form">
          <div className="form-group">
            <label htmlFor="household-size-input">Household Size (Portions)</label>
            <input
              id="household-size-input"
              type="number"
              min="1"
              max="20"
              className="number-input"
              aria-label="Household Size"
              value={householdSize}
              onChange={(e) => setHouseholdSize(e.target.value)}
              required
            />
            <span className="field-hint">
              Used as default portion count when scheduling recipes and calculating ingredient amounts.
            </span>
          </div>

          <div className="form-group">
            <label htmlFor="meals-per-week-input">Meals Per Week Target</label>
            <input
              id="meals-per-week-input"
              type="number"
              min="1"
              max="21"
              className="number-input"
              aria-label="Meals Per Week"
              value={mealsPerWeek}
              onChange={(e) => setMealsPerWeek(e.target.value)}
              required
            />
            <span className="field-hint">
              Target number of home-cooked meals planned each week (used in planner progress indicators).
            </span>
          </div>

          <div className="form-group">
            <label>Preferred Cooking Days</label>
            <div className="day-pills-row" role="group" aria-label="Preferred cooking days">
              {ALL_DAYS.map((day) => {
                const isSelected = preferredDays.includes(day.key);
                return (
                  <button
                    key={day.key}
                    type="button"
                    className={`day-toggle-pill ${isSelected ? "selected" : ""}`}
                    onClick={() => toggleDay(day.key)}
                    aria-pressed={isSelected}
                  >
                    {day.label}
                  </button>
                );
              })}
            </div>
            <span className="field-hint">
              Days auto-populate will prioritize when assigning weekly recipes.
            </span>
          </div>

          <div className="settings-actions">
            <button
              type="submit"
              className="btn-primary"
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : "Save Settings"}
            </button>
            {successMessage && (
              <span className="success-inline" role="status">
                {successMessage}
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};
