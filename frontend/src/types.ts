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

export interface ReceiptItem {
  raw_name?: string;
  name: string;
  matched_item_id?: number | null;
  suggested_location?: "pantry" | "fridge" | "freezer";
  quantity: number;
  unit?: string;
  price: number;
  category?: string | null;
  include?: boolean;
}

export interface ReceiptParsedData {
  store: string;
  date: string;
  total: number;
  currency: string;
  items: ReceiptItem[];
}

export interface ReceiptCommitItem {
  name: string;
  category?: string | null;
  location: "pantry" | "fridge" | "freezer";
  quantity: number;
  unit?: string;
  price: number;
  include_inventory: boolean;
  include_price: boolean;
}

export interface ReceiptCommitPayload {
  date: string;
  currency: string;
  record_spend: boolean;
  total_spend: number;
  items: ReceiptCommitItem[];
}

export interface ReceiptCommitResponse {
  status: string;
  inventory_items_added: number;
  prices_updated: number;
  spend_recorded: number;
}
