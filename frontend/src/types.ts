export interface Settings {
  household_size: number;
  meals_per_week: number;
  preferred_days: string;
}

export interface Item {
  id: number;
  name: string;
  category?: string | null;
}

export interface InventoryItem {
  id: number;
  item_id: number;
  item_name: string;
  location: "pantry" | "fridge" | "freezer" | string;
  quantity: number;
  unit?: string;
  updated_at?: string;
}

export interface Ingredient {
  id?: number;
  item_id?: number;
  item_name?: string | null;
  raw?: string;
  name?: string | null;
  quantity?: number | null;
  unit?: string;
  staple?: boolean;
}

export interface Recipe {
  id: number;
  title: string;
  servings: number;
  source_url?: string | null;
  steps?: string[];
  total_time?: string | null;
  needs_review: boolean;
  review_notes?: string | null;
  ingredients: Ingredient[];
  created_at?: string;
}

export interface RecipePatchPayload {
  title?: string;
  servings?: number;
  steps?: string[];
  total_time?: string | null;
  needs_review?: boolean;
  review_notes?: string | null;
  ingredients?: Ingredient[];
}

export interface PlanEntry {
  id: number;
  recipe_id: number;
  title?: string;
  recipe_title?: string;
  date: string;
  slot?: string | null;
  servings_override?: number | null;
  cooked?: boolean | number;
}

export interface GroceryLine {
  item_id: number;
  name: string;
  quantity: number | null;
  unit: string;
  current_inventory?: number;
  price?: number | null;
  price_currency?: string | null;
  currency?: string | null;
  price_source?: string | null;
}

export interface BudgetSummary {
  week_start: string;
  target: number;
  currency: string;
  estimated?: number;
  actual?: number;
  remaining?: number;
  list_estimated_cost?: number;
  actual_spend?: number;
  lines?: GroceryLine[];
}

export type ViewTab =
  | "planner"
  | "grocery-list"
  | "calendar"
  | "cookbook"
  | "kitchen"
  | "budget"
  | "settings";
