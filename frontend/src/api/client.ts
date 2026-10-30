import type {
  Settings,
  Item,
  InventoryItem,
  Recipe,
  RecipePatchPayload,
  PlanEntry,
  GroceryLine,
  BudgetSummary,
  ReceiptParsedData,
  ReceiptCommitPayload,
  ReceiptCommitResponse,
} from "../types";
import { getMonday } from "../utils/date";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  };
  const response = await fetch(path, {
    ...options,
    ...(Object.keys(headers).length > 0 ? { headers } : {}),
  });
  if (!response.ok) {
    let errMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const data = await response.json();
      if (data?.detail) {
        errMessage =
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail);
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(errMessage);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSettings(): Promise<Settings> {
    return request<Settings>("/settings");
  },

  async putSettings(
    s: Partial<Settings> | { key: string; value: string }
  ): Promise<{ ok: boolean }> {
    if ("key" in s && "value" in s) {
      return request<{ ok: boolean }>("/settings", {
        method: "PUT",
        body: JSON.stringify(s),
      });
    }
    for (const [k, v] of Object.entries(s)) {
      if (v !== undefined) {
        await request<{ ok: boolean }>("/settings", {
          method: "PUT",
          body: JSON.stringify({ key: k, value: String(v) }),
        });
      }
    }
    return { ok: true };
  },

  getRecipes(needsReview?: boolean): Promise<Recipe[]> {
    const url =
      needsReview !== undefined
        ? `/recipes?needs_review=${needsReview}`
        : "/recipes";
    return request<Recipe[]>(url);
  },

  getRecipe(id: number): Promise<Recipe> {
    return request<Recipe>(`/recipes/${id}`);
  },

  ingestRecipe(body: {
    url?: string;
    raw_text?: string;
    title?: string;
  }): Promise<Recipe> {
    return request<Recipe>("/recipes/ingest", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  reingestRecipe(id: number, rawText: string): Promise<Recipe> {
    return request<Recipe>(`/recipes/${id}/reingest`, {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText }),
    });
  },

  patchRecipe(
    id: number,
    body: Partial<RecipePatchPayload>
  ): Promise<Recipe> {
    return request<Recipe>(`/recipes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteRecipe(id: number): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/recipes/${id}`, {
      method: "DELETE",
    });
  },

  getPlan(weekStart: string): Promise<PlanEntry[]> {
    return request<PlanEntry[]>(`/plan?week_start=${encodeURIComponent(weekStart)}`);
  },

  getPlanRange(startDate: string, endDate: string): Promise<PlanEntry[]> {
    return request<PlanEntry[]>(
      `/plan?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`
    );
  },

  addPlanEntry(body: {
    recipe_id: number;
    date: string;
    slot?: string | null;
    servings_override?: number | null;
  }): Promise<{ entry_id: number }> {
    return request<{ entry_id: number }>("/plan", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  deletePlanEntry(id: number): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/plan/${id}`, {
      method: "DELETE",
    });
  },

  markCooked(id: number): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/plan/${id}/cooked`, {
      method: "POST",
    });
  },

  autoPopulate(weekStart: string): Promise<{ entry_ids: number[] }> {
    return request<{ entry_ids: number[] }>("/plan/auto-populate", {
      method: "POST",
      body: JSON.stringify({ week_start: weekStart }),
    });
  },

  getList(weekStart: string): Promise<GroceryLine[]> {
    return request<GroceryLine[]>(
      `/list?week_start=${encodeURIComponent(weekStart)}`
    );
  },

  async getInventory(location?: string): Promise<InventoryItem[]> {
    const url = location
      ? `/inventory?location=${encodeURIComponent(location)}`
      : "/inventory";
    const items = await request<InventoryItem[]>(url);
    if (location) {
      return items.filter((i) => i.location === location);
    }
    return items;
  },

  addInventory(body: {
    item_id?: number;
    name?: string;
    location: string;
    quantity: number;
    unit?: string;
  }): Promise<{ inventory_id: number }> {
    return request<{ inventory_id: number }>("/inventory", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  patchInventory(
    id: number,
    delta: number
  ): Promise<{ quantity: number }> {
    return request<{ quantity: number }>(`/inventory/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ delta }),
    });
  },

  deleteInventory(id: number): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/inventory/${id}`, {
      method: "DELETE",
    });
  },

  getItems(): Promise<Item[]> {
    return request<Item[]>("/items");
  },

  createItem(body: {
    name: string;
    category?: string | null;
  }): Promise<{ item_id: number }> {
    return request<{ item_id: number }>("/items", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getBudget(weekStart: string): Promise<BudgetSummary> {
    return request<BudgetSummary>(
      `/budget/${encodeURIComponent(weekStart)}`
    );
  },

  putBudget(
    weekStart: string,
    body: { target: number; currency?: string }
  ): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(
      `/budget/${encodeURIComponent(weekStart)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      }
    );
  },

  postSpend(
    body: {
      price: number;
      currency: string;
      date: string;
      source?: string;
      item_id?: number | null;
    },
    weekStart?: string
  ): Promise<{ ok: boolean }> {
    const ws = weekStart || getMonday(body.date);
    return request<{ ok: boolean }>(`/budget/${encodeURIComponent(ws)}/spend`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  postOwnPrice(body: {
    item_id: number;
    price: number;
    currency: string;
    date: string;
    package_quantity?: number;
    package_unit?: string;
  }): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>("/prices/own", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  postEstimate(body: {
    item_id?: number | null;
    category?: string | null;
    price: number;
    currency: string;
    package_quantity?: number;
    package_unit?: string;
  }): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>("/prices/estimate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  parseReceipt(file: File): Promise<ReceiptParsedData> {
    const formData = new FormData();
    formData.append("file", file);
    return request<ReceiptParsedData>("/receipts/parse", {
      method: "POST",
      body: formData,
    });
  },

  commitReceipt(payload: ReceiptCommitPayload): Promise<ReceiptCommitResponse> {
    return request<ReceiptCommitResponse>("/receipts/commit", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
