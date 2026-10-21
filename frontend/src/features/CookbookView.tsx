import React, { useState, useEffect, useCallback } from "react";
import type { Recipe } from "../types";
import { api } from "../api/client";
import { RecipeModal } from "./RecipeModal";

interface CookbookViewProps {
  recipes?: Recipe[];
  onRefresh?: () => Promise<void> | void;
  onError?: (msg: string | null) => void;
}

export const CookbookView: React.FC<CookbookViewProps> = ({
  recipes: initialRecipes = [],
  onRefresh,
  onError,
}) => {
  const [recipes, setRecipes] = useState<Recipe[]>(initialRecipes);
  const [activeFilter, setActiveFilter] = useState<"all" | "review">("all");
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Ingest form state
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [showRawText, setShowRawText] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);

  const loadRecipes = useCallback(
    async (filter: "all" | "review") => {
      setIsLoading(true);
      try {
        const data = await api.getRecipes(filter === "review" ? true : undefined);
        setRecipes(data);
      } catch (err: any) {
        onError?.(err.message || "Failed to load recipes");
      } finally {
        setIsLoading(false);
      }
    },
    [onError]
  );

  useEffect(() => {
    loadRecipes(activeFilter);
  }, [activeFilter, loadRecipes]);

  // Sync if initialRecipes prop changes and we are on "all"
  useEffect(() => {
    if (activeFilter === "all" && initialRecipes.length > 0) {
      setRecipes(initialRecipes);
    }
  }, [initialRecipes, activeFilter]);

  const reviewQueueCount = recipes.filter((r) => r.needs_review).length;

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() && !rawText.trim()) {
      onError?.("Please provide a recipe URL or paste recipe text.");
      return;
    }

    setIsIngesting(true);
    try {
      const ingested = await api.ingestRecipe({
        url: url.trim() || undefined,
        raw_text: rawText.trim() || undefined,
        title: title.trim() || undefined,
      });

      setUrl("");
      setTitle("");
      setRawText("");
      setShowRawText(false);

      await onRefresh?.();
      await loadRecipes(activeFilter);

      if (ingested.needs_review && activeFilter === "all") {
        // Optionally notify or prompt
      }
    } catch (err: any) {
      onError?.(err.message || "Failed to ingest recipe");
    } finally {
      setIsIngesting(false);
    }
  };

  const handleOpenRecipe = async (recipe: Recipe) => {
    try {
      const full = await api.getRecipe(recipe.id);
      setSelectedRecipe(full);
    } catch {
      // Fallback to existing recipe item
      setSelectedRecipe(recipe);
    }
  };

  const handleRecipeSaved = (updated: Recipe, closeAfter = true) => {
    setRecipes((prev) =>
      prev.map((r) => (r.id === updated.id ? updated : r))
    );
    if (closeAfter) {
      setSelectedRecipe(null);
    } else {
      setSelectedRecipe(updated);
    }
    onRefresh?.();
    loadRecipes(activeFilter);
  };

  const handleRecipeDeleted = (id: number) => {
    setRecipes((prev) => prev.filter((r) => r.id !== id));
    setSelectedRecipe(null);
    onRefresh?.();
  };

  const filteredRecipes =
    activeFilter === "review"
      ? recipes.filter((r) => r.needs_review)
      : recipes;

  return (
    <div className="cookbook-view">
      {/* Ingest Bar */}
      <section className="cookbook-ingest-card">
        <header className="ingest-header">
          <h2>Import Recipe</h2>
          <p className="ingest-subtitle">
            Paste a recipe URL (webpage or video) or paste raw recipe text.
          </p>
        </header>

        <form onSubmit={handleIngest} className="ingest-form">
          <div className="ingest-inputs">
            <input
              type="url"
              className="text-input flex-2"
              placeholder="https://..."
              aria-label="Recipe URL"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <input
              type="text"
              className="text-input flex-1"
              placeholder="Optional title override"
              aria-label="Title override"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={isIngesting || (!url.trim() && !rawText.trim())}
            >
              {isIngesting ? "Importing..." : "Import Recipe"}
            </button>
          </div>

          <div className="ingest-toggle-row">
            <button
              type="button"
              className="btn-link-subtle"
              onClick={() => setShowRawText((prev) => !prev)}
            >
              {showRawText ? "− Hide pasted text" : "+ Paste raw recipe text / caption"}
            </button>
          </div>

          {showRawText && (
            <textarea
              className="text-input raw-text-area"
              rows={4}
              placeholder="Paste recipe ingredients, instructions, or social media caption..."
              aria-label="Raw recipe text"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          )}
        </form>
      </section>

      {/* Filter Tabs */}
      <div className="cookbook-toolbar">
        <div className="tab-pill-group">
          <button
            type="button"
            className={`tab-pill ${activeFilter === "all" ? "active" : ""}`}
            onClick={() => setActiveFilter("all")}
          >
            All Recipes
          </button>
          <button
            type="button"
            className={`tab-pill ${activeFilter === "review" ? "active" : ""}`}
            onClick={() => setActiveFilter("review")}
          >
            Review Queue
            {reviewQueueCount > 0 && (
              <span className="pill-badge">{reviewQueueCount}</span>
            )}
          </button>
        </div>
      </div>

      {/* Recipe List */}
      {isLoading ? (
        <div className="loading-indicator">Loading recipes...</div>
      ) : filteredRecipes.length === 0 ? (
        <div className="empty-state">
          {activeFilter === "review" ? (
            <p>No recipes currently need review! Everything is tidy. 🎉</p>
          ) : (
            <p>No recipes found. Import one using the bar above!</p>
          )}
        </div>
      ) : (
        <div className="recipe-grid">
          {filteredRecipes.map((recipe) => (
            <div key={recipe.id} className="recipe-card">
              <div className="recipe-card-header">
                <h3 className="recipe-card-title">{recipe.title}</h3>
                {recipe.needs_review && (
                  <span className="badge badge-warning">Needs Review</span>
                )}
              </div>

              <div className="recipe-card-meta">
                <span>🍽️ {recipe.servings} servings</span>
                {recipe.total_time && <span>⏱️ {recipe.total_time}</span>}
                {recipe.ingredients && (
                  <span>🥗 {recipe.ingredients.length} ingredients</span>
                )}
              </div>

              {recipe.needs_review && recipe.review_notes && (
                <p className="recipe-card-notes">{recipe.review_notes}</p>
              )}

              <div className="recipe-card-actions">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => handleOpenRecipe(recipe)}
                >
                  Edit / Review
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal Dialog */}
      {selectedRecipe && (
        <RecipeModal
          recipe={selectedRecipe}
          onClose={() => setSelectedRecipe(null)}
          onSave={handleRecipeSaved}
          onDelete={handleRecipeDeleted}
          onError={onError}
        />
      )}
    </div>
  );
};
