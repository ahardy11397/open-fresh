import React, { useState, useEffect, useCallback } from "react";
import { api } from "./api/client";
import type { ViewTab, Settings, Recipe } from "./types";
import { getMonday } from "./utils/date";
import { PlannerView } from "./features/PlannerView";
import { GroceryListView } from "./features/GroceryListView";
import { CalendarView } from "./features/CalendarView";
import { CookbookView } from "./features/CookbookView";
import { KitchenView } from "./features/KitchenView";
import { BudgetView } from "./features/BudgetView";
import { SettingsView } from "./features/SettingsView";
import "./styles.css";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ViewTab>("planner");
  const [weekStart, setWeekStart] = useState<string>(() =>
    getMonday(new Date())
  );
  const [settings, setSettings] = useState<Settings | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadInitialData = useCallback(async () => {
    try {
      const [settingsData, recipesData] = await Promise.all([
        api.getSettings().catch(() => null),
        api.getRecipes().catch(() => []),
      ]);
      if (settingsData) setSettings(settingsData);
      if (recipesData) setRecipes(recipesData);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load initial data");
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const handleNavigateToWeek = (targetWeekStart: string) => {
    setWeekStart(targetWeekStart);
    setActiveTab("planner");
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-brand">
          <span className="app-logo">🥗</span>
          <span className="app-title">Open-fresh</span>
        </div>

        <nav className="app-nav" aria-label="Main Navigation">
          <button
            type="button"
            className={`nav-tab ${activeTab === "planner" ? "active" : ""}`}
            onClick={() => setActiveTab("planner")}
          >
            Planner
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "grocery-list" ? "active" : ""}`}
            onClick={() => setActiveTab("grocery-list")}
          >
            Grocery List
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "calendar" ? "active" : ""}`}
            onClick={() => setActiveTab("calendar")}
          >
            Calendar
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "cookbook" ? "active" : ""}`}
            onClick={() => setActiveTab("cookbook")}
          >
            Cookbook
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "kitchen" ? "active" : ""}`}
            onClick={() => setActiveTab("kitchen")}
          >
            Kitchen
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "budget" ? "active" : ""}`}
            onClick={() => setActiveTab("budget")}
          >
            Budget
          </button>
          <button
            type="button"
            className={`nav-tab ${activeTab === "settings" ? "active" : ""}`}
            onClick={() => setActiveTab("settings")}
          >
            Settings
          </button>
        </nav>
      </header>

      {errorMessage && (
        <div className="error-banner" role="alert">
          <span>{errorMessage}</span>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      <main className="app-main">
        {activeTab === "planner" && (
          <PlannerView
            weekStart={weekStart}
            setWeekStart={setWeekStart}
            settings={settings}
            recipes={recipes}
            onError={setErrorMessage}
          />
        )}
        {activeTab === "grocery-list" && (
          <GroceryListView
            weekStart={weekStart}
            onError={setErrorMessage}
          />
        )}
        {activeTab === "calendar" && (
          <CalendarView
            weekStart={weekStart}
            onNavigateToWeek={handleNavigateToWeek}
            onError={setErrorMessage}
          />
        )}
        {activeTab === "cookbook" && (
          <CookbookView
            recipes={recipes}
            onRefresh={loadInitialData}
            onError={setErrorMessage}
          />
        )}
        {activeTab === "kitchen" && (
          <KitchenView onError={setErrorMessage} />
        )}
        {activeTab === "budget" && (
          <BudgetView weekStart={weekStart} onError={setErrorMessage} />
        )}
        {activeTab === "settings" && (
          <SettingsView
            settings={settings}
            onRefresh={loadInitialData}
            onError={setErrorMessage}
          />
        )}
      </main>
    </div>
  );
};

export default App;
