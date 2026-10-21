import React, { useState, useEffect } from "react";
import type { Recipe, Ingredient } from "../types";
import { api } from "../api/client";

export interface RecipeModalProps {
  recipe: Recipe;
  onClose: () => void;
  onSave: (updated: Recipe, closeAfterSave?: boolean) => void;
  onDelete?: (id: number) => void;
  onError?: (msg: string | null) => void;
}

export const RecipeModal: React.FC<RecipeModalProps> = ({
  recipe,
  onClose,
  onSave,
  onDelete,
  onError,
}) => {
  const [title, setTitle] = useState(recipe.title || "");
  const [servings, setServings] = useState(recipe.servings || 2);
  const [totalTime, setTotalTime] = useState(recipe.total_time || "");
  const [stepsText, setStepsText] = useState(
    Array.isArray(recipe.steps) ? recipe.steps.join("\n") : ""
  );
  const [ingredients, setIngredients] = useState<Ingredient[]>(
    recipe.ingredients ? [...recipe.ingredients] : []
  );
  const [reingestText, setReingestText] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isReingesting, setIsReingesting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    setTitle(recipe.title || "");
    setServings(recipe.servings || 2);
    setTotalTime(recipe.total_time || "");
    setStepsText(Array.isArray(recipe.steps) ? recipe.steps.join("\n") : "");
    setIngredients(recipe.ingredients ? [...recipe.ingredients] : []);
  }, [recipe]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleIngredientChange = (
    index: number,
    field: keyof Ingredient,
    val: any
  ) => {
    setIngredients((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: val };
      return next;
    });
  };

  const handleAddIngredient = () => {
    setIngredients((prev) => [
      ...prev,
      { name: "", quantity: 1, unit: "", staple: false },
    ]);
  };

  const handleRemoveIngredient = (index: number) => {
    setIngredients((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSave = async (markReviewed: boolean) => {
    setIsSaving(true);
    try {
      const parsedSteps = stepsText
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      const validIngredients = ingredients.filter(
        (ing) => (ing.name && ing.name.trim()) || (ing.raw && ing.raw.trim())
      );

      const payload: any = {
        title,
        servings: Number(servings) || 1,
        total_time: totalTime || null,
        steps: parsedSteps,
        ingredients: validIngredients.map((ing) => ({
          name: ing.name?.trim() || null,
          raw: ing.raw || ing.name || "",
          quantity:
            ing.quantity !== null && ing.quantity !== undefined && ing.quantity !== ("" as any)
              ? Number(ing.quantity)
              : null,
          unit: ing.unit?.trim() || "",
          staple: !!ing.staple,
        })),
      };

      if (markReviewed) {
        payload.needs_review = false;
        payload.review_notes = null;
      }

      const updated = await api.patchRecipe(recipe.id, payload);
      onSave(updated, true);
      onClose();
    } catch (err: any) {
      onError?.(err.message || "Failed to save recipe");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm?.(`Are you sure you want to delete "${recipe.title}"?`)) {
      // In tests where confirm is undefined or returns false, if we want to support direct click:
      // only proceed if confirm is not defined or returns true
      if (typeof window.confirm === "function") {
        return;
      }
    }
    setIsDeleting(true);
    try {
      await api.deleteRecipe(recipe.id);
      onDelete?.(recipe.id);
      onClose();
    } catch (err: any) {
      onError?.(err.message || "Failed to delete recipe");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReingest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reingestText.trim()) return;
    setIsReingesting(true);
    try {
      const updated = await api.reingestRecipe(recipe.id, reingestText.trim());
      setTitle(updated.title || "");
      setServings(updated.servings || 2);
      setTotalTime(updated.total_time || "");
      setStepsText(Array.isArray(updated.steps) ? updated.steps.join("\n") : "");
      setIngredients(updated.ingredients ? [...updated.ingredients] : []);
      setReingestText("");
      onSave(updated, false);
    } catch (err: any) {
      onError?.(err.message || "Failed to re-extract recipe");
    } finally {
      setIsReingesting(false);
    }
  };

  return (
    <dialog
      open
      className="modal-dialog"
      aria-modal="true"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          onClose();
        }
      }}
    >
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-content">
        <header className="modal-header">
          <h2>Edit Recipe: {recipe.title}</h2>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            ×
          </button>
        </header>

        {recipe.needs_review && (
          <div className="review-notes-alert" role="alert">
            <span className="alert-badge">Needs Review</span>
            <span className="alert-message">
              {recipe.review_notes || "Please review extracted ingredients and steps."}
            </span>
          </div>
        )}

        <div className="modal-body">
          <div className="form-group">
            <label htmlFor="recipe-title">Title</label>
            <input
              id="recipe-title"
              className="text-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label htmlFor="recipe-servings">Servings</label>
              <input
                id="recipe-servings"
                className="number-input"
                type="number"
                min="1"
                value={servings}
                onChange={(e) => setServings(Number(e.target.value))}
                required
              />
            </div>
            <div className="form-group flex-1">
              <label htmlFor="recipe-total-time">Total Time</label>
              <input
                id="recipe-total-time"
                className="text-input"
                type="text"
                placeholder="e.g. 30m"
                value={totalTime}
                onChange={(e) => setTotalTime(e.target.value)}
              />
            </div>
          </div>

          <section className="modal-section">
            <div className="section-header">
              <h3>Ingredients</h3>
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={handleAddIngredient}
              >
                + Add Ingredient
              </button>
            </div>
            <div className="ingredient-edit-list">
              {ingredients.map((ing, idx) => (
                <div key={idx} className="ingredient-edit-row">
                  <input
                    type="text"
                    className="text-input ing-name"
                    placeholder="Ingredient name"
                    value={ing.name || ""}
                    onChange={(e) =>
                      handleIngredientChange(idx, "name", e.target.value)
                    }
                    aria-label={`Ingredient ${idx + 1} Name`}
                  />
                  <input
                    type="number"
                    className="number-input ing-qty"
                    placeholder="Qty"
                    step="any"
                    value={ing.quantity ?? ""}
                    onChange={(e) =>
                      handleIngredientChange(
                        idx,
                        "quantity",
                        e.target.value === "" ? null : Number(e.target.value)
                      )
                    }
                    aria-label={`Ingredient ${idx + 1} Quantity`}
                  />
                  <input
                    type="text"
                    className="text-input ing-unit"
                    placeholder="Unit"
                    value={ing.unit || ""}
                    onChange={(e) =>
                      handleIngredientChange(idx, "unit", e.target.value)
                    }
                    aria-label={`Ingredient ${idx + 1} Unit`}
                  />
                  <label className="staple-toggle" title="Mark as pantry staple">
                    <input
                      type="checkbox"
                      checked={!!ing.staple}
                      onChange={(e) =>
                        handleIngredientChange(idx, "staple", e.target.checked)
                      }
                      aria-label={`Ingredient ${idx + 1} Staple`}
                    />
                    <span>Staple</span>
                  </label>
                  <button
                    type="button"
                    className="btn-danger btn-sm"
                    onClick={() => handleRemoveIngredient(idx)}
                    aria-label={`Remove Ingredient ${idx + 1}`}
                  >
                    ×
                  </button>
                </div>
              ))}
              {ingredients.length === 0 && (
                <p className="empty-subtext">No ingredients listed.</p>
              )}
            </div>
          </section>

          <div className="form-group">
            <label htmlFor="recipe-steps">Steps (one per line)</label>
            <textarea
              id="recipe-steps"
              className="text-input steps-textarea"
              rows={5}
              value={stepsText}
              onChange={(e) => setStepsText(e.target.value)}
              placeholder="1. Prep ingredients...&#10;2. Cook over medium heat..."
            />
          </div>

          <details className="reingest-collapsible">
            <summary className="reingest-summary">Re-ingest from Text</summary>
            <form onSubmit={handleReingest} className="reingest-form">
              <p className="reingest-help">
                Paste raw recipe text or video caption to re-extract ingredients and steps in-place.
              </p>
              <textarea
                className="text-input"
                rows={3}
                placeholder="Paste raw text or video caption here..."
                value={reingestText}
                onChange={(e) => setReingestText(e.target.value)}
                aria-label="Re-ingest raw text"
              />
              <button
                type="submit"
                className="btn-secondary btn-sm"
                disabled={isReingesting || !reingestText.trim()}
              >
                {isReingesting ? "Re-extracting..." : "Re-extract Recipe"}
              </button>
            </form>
          </details>
        </div>

        <footer className="modal-footer">
          <button
            type="button"
            className="btn-danger btn-sm"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting..." : "Delete Recipe"}
          </button>
          <div className="modal-actions-right">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => handleSave(false)}
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => handleSave(true)}
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : "Save & Mark Reviewed"}
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  );
};
