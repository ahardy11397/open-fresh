import React from "react";
import type { Recipe } from "../types";

interface CookbookViewProps {
  recipes?: Recipe[];
  onRefresh?: () => void;
  onError?: (msg: string) => void;
}

export const CookbookView: React.FC<CookbookViewProps> = () => {
  return (
    <div className="surface-placeholder">
      <h2>Cookbook & Review Queue</h2>
      <p>Recipe management and ingest view will be expanded in Task 3.</p>
    </div>
  );
};
