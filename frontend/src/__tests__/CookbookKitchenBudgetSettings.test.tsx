import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

describe("Cookbook, Kitchen, Budget, and Settings surfaces", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("test_cookbook_ingest_and_review_queue_resolve", async () => {
    const user = userEvent.setup();

    let recipesData = [
      {
        id: 1,
        title: "Garlic Pasta",
        servings: 2,
        total_time: "20m",
        needs_review: false,
        review_notes: null,
        ingredients: [{ name: "garlic", quantity: 4, unit: "cloves" }],
        steps: ["Boil pasta", "Sauté garlic"],
      },
    ];

    const patchRequests: { url: string; body: any }[] = [];
    const postRequests: { url: string; body: any }[] = [];

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || "GET";

      if (url.includes("/settings")) {
        return {
          ok: true,
          json: async () => ({
            household_size: 2,
            meals_per_week: 5,
            preferred_days: "mon,tue,wed,thu,fri",
          }),
        } as Response;
      }

      if (url.includes("/recipes/ingest") && method === "POST") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        postRequests.push({ url, body });
        const newRecipe = {
          id: 2,
          title: "Imported Chili",
          servings: 4,
          total_time: "45m",
          needs_review: true,
          review_notes: "Missing unit on beans",
          ingredients: [{ item_name: "beans", raw: "2 beans", quantity: 2, unit: "" }],
          steps: ["Boil beans"],
        };
        recipesData.push(newRecipe);
        return {
          ok: true,
          json: async () => newRecipe,
        } as Response;
      }

      if (url.includes("/recipes/2") && method === "PATCH") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        patchRequests.push({ url, body });
        const updated = {
          id: 2,
          title: body.title || "Imported Chili (Updated)",
          servings: body.servings ?? 4,
          total_time: body.total_time ?? "45m",
          needs_review: body.needs_review ?? false,
          review_notes: body.review_notes ?? null,
          ingredients: body.ingredients ?? [{ name: "beans", quantity: 2, unit: "can" }],
          steps: body.steps ?? ["Boil beans", "Simmer 20m"],
        };
        recipesData = recipesData.map((r) => (r.id === 2 ? updated : r));
        return {
          ok: true,
          json: async () => updated,
        } as Response;
      }

      if (url.match(/\/recipes\/2$/) && method === "GET") {
        const r2 = recipesData.find((r) => r.id === 2);
        return {
          ok: true,
          json: async () => r2 || {
            id: 2,
            title: "Imported Chili",
            servings: 4,
            total_time: "45m",
            needs_review: true,
            review_notes: "Missing unit on beans",
            ingredients: [{ item_name: "beans", raw: "2 beans", quantity: 2, unit: "" }],
            steps: ["Boil beans"],
          },
        } as Response;
      }

      if (url.includes("/recipes") && method === "GET") {
        if (url.includes("needs_review=true")) {
          return {
            ok: true,
            json: async () => recipesData.filter((r) => r.needs_review),
          } as Response;
        }
        return {
          ok: true,
          json: async () => recipesData,
        } as Response;
      }

      if (url.includes("/plan")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/list")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/budget")) {
        return {
          ok: true,
          json: async () => ({
            week_start: "2026-10-19",
            target: 100,
            currency: "USD",
            estimated: 0,
            actual: 0,
            remaining: 100,
          }),
        } as Response;
      }

      if (url.includes("/inventory")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });

    render(<App />);

    // Switch to Cookbook tab
    const cookbookNav = screen.getByRole("button", { name: "Cookbook" });
    await user.click(cookbookNav);

    // Verify Cookbook view loaded
    await waitFor(() => {
      expect(screen.getByText("Garlic Pasta")).toBeInTheDocument();
    });

    // Ingest a new recipe via URL
    const urlInput = screen.getByPlaceholderText(/https:\/\//i);
    await user.type(urlInput, "https://example.com/recipes/chili");

    const importBtn = screen.getByRole("button", { name: /Import Recipe/i });
    await user.click(importBtn);

    // Verify POST /recipes/ingest was called
    await waitFor(() => {
      const ingestCall = postRequests.find((r) => r.url.includes("/recipes/ingest"));
      expect(ingestCall).toBeDefined();
      expect(ingestCall?.body.url).toBe("https://example.com/recipes/chili");
    });

    // Switch to Review Queue tab
    const reviewQueueTab = screen.getByRole("button", { name: /Review Queue/i });
    await user.click(reviewQueueTab);

    // Verify "Imported Chili" appears in Review Queue
    await waitFor(() => {
      expect(screen.getByText("Imported Chili")).toBeInTheDocument();
    });

    // Open RecipeModal by clicking "Edit / Review" (or recipe title/card)
    const reviewBtn = screen.getByRole("button", { name: /Edit \/ Review/i });
    await user.click(reviewBtn);

    // Verify RecipeModal dialog opened with review notes banner and ingredient name populated
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Missing unit on beans");
      expect(screen.getByLabelText("Ingredient 1 Name")).toHaveValue("beans");
    });

    // Edit title
    const titleInput = screen.getByLabelText(/^Title$/i);
    await user.clear(titleInput);
    await user.type(titleInput, "Imported Chili (Updated)");

    // Edit steps textarea
    const stepsInput = screen.getByLabelText(/Steps/i);
    await user.clear(stepsInput);
    await user.type(stepsInput, "Boil beans\nSimmer 20m");

    // Click "+ Add Ingredient" (adds a blank ingredient row)
    const addIngBtn = screen.getByRole("button", { name: /\+ Add Ingredient/i });
    await user.click(addIngBtn);

    // Click "Save & Mark Reviewed"
    const saveReviewedBtn = screen.getByRole("button", { name: /Save & Mark Reviewed/i });
    await user.click(saveReviewedBtn);

    // Verify PATCH /recipes/2 was called with needs_review: false and review_notes: null
    // and that blank ingredient row was filtered out
    await waitFor(() => {
      const patchCall = patchRequests.find((r) => r.url.includes("/recipes/2"));
      expect(patchCall).toBeDefined();
      expect(patchCall?.body.needs_review).toBe(false);
      expect(patchCall?.body.review_notes).toBeNull();
      expect(patchCall?.body.title).toBe("Imported Chili (Updated)");
      expect(patchCall?.body.ingredients).toHaveLength(1);
      expect(patchCall?.body.ingredients[0].name).toBe("beans");
    });

    // Switch to "All Recipes" tab, reopen modal and test Escape key closes it
    const allRecipesTab = screen.getByRole("button", { name: /All Recipes/i });
    await user.click(allRecipesTab);

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /Edit \/ Review/i }).length).toBeGreaterThan(0);
    });

    const reopenBtn = screen.getAllByRole("button", { name: /Edit \/ Review/i })[0];
    await user.click(reopenBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("test_kitchen_inventory_tabs_and_steppers", async () => {
    const user = userEvent.setup();

    const patchRequests: { url: string; body: any }[] = [];

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || "GET";

      if (url.includes("/settings")) {
        return {
          ok: true,
          json: async () => ({
            household_size: 2,
            meals_per_week: 5,
            preferred_days: "mon,tue,wed,thu,fri",
          }),
        } as Response;
      }

      if (url.includes("/recipes")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/plan")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/inventory/10") && method === "PATCH") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        patchRequests.push({ url, body });
        return {
          ok: true,
          json: async () => ({ quantity: 3 }),
        } as Response;
      }

      if (url.includes("/inventory/11") && method === "PATCH") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        patchRequests.push({ url, body });
        return {
          ok: true,
          json: async () => ({ quantity: 0 }),
        } as Response;
      }

      if (url.includes("/inventory")) {
        if (url.includes("location=fridge")) {
          return {
            ok: true,
            json: async () => [
              {
                id: 11,
                item_id: 2,
                item_name: "Milk",
                location: "fridge",
                quantity: 1,
                unit: "carton",
              },
            ],
          } as Response;
        }
        // Default pantry
        return {
          ok: true,
          json: async () => [
            {
              id: 10,
              item_id: 1,
              item_name: "Olive Oil",
              location: "pantry",
              quantity: 2,
              unit: "bottle",
            },
          ],
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });

    render(<App />);

    // Switch to Kitchen tab
    const kitchenNav = screen.getByRole("button", { name: "Kitchen" });
    await user.click(kitchenNav);

    // Verify Pantry items load
    await waitFor(() => {
      expect(screen.getByText("Olive Oil")).toBeInTheDocument();
      expect(screen.getByText(/2 bottle/i)).toBeInTheDocument();
    });

    // Click "+" stepper on Olive Oil
    const plusBtn = screen.getByRole("button", { name: "Increase Olive Oil" });
    await user.click(plusBtn);

    await waitFor(() => {
      const patchCall = patchRequests.find((r) => r.url.includes("/inventory/10"));
      expect(patchCall).toBeDefined();
      expect(patchCall?.body.delta).toBe(1);
    });

    // Switch to Fridge tab
    const fridgeTab = screen.getByRole("button", { name: "Fridge" });
    await user.click(fridgeTab);

    // Verify Milk appears
    await waitFor(() => {
      expect(screen.getByText("Milk")).toBeInTheDocument();
      expect(screen.getByText(/1 carton/i)).toBeInTheDocument();
    });

    // Click "−" stepper on Milk
    const minusBtn = screen.getByRole("button", { name: "Decrease Milk" });
    await user.click(minusBtn);

    await waitFor(() => {
      const patchCall = patchRequests.find((r) => r.url.includes("/inventory/11"));
      expect(patchCall).toBeDefined();
      expect(patchCall?.body.delta).toBe(-1);
    });
  });

  it("test_budget_and_settings_update", async () => {
    const user = userEvent.setup();

    const putRequests: { url: string; body: any }[] = [];

    let currentSettings = {
      household_size: 2,
      meals_per_week: 5,
      preferred_days: "mon,tue,wed,thu,fri",
    };

    let currentBudget = {
      week_start: "2026-10-19",
      target: 120,
      currency: "USD",
      estimated: 45,
      actual: 20,
      remaining: 100,
    };

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || "GET";

      if (url.includes("/settings") && method === "PUT") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        putRequests.push({ url, body });
        if (body.key && body.value) {
          (currentSettings as any)[body.key] = isNaN(Number(body.value))
            ? body.value
            : Number(body.value);
        }
        return {
          ok: true,
          json: async () => ({ ok: true }),
        } as Response;
      }

      if (url.includes("/settings") && method === "GET") {
        return {
          ok: true,
          json: async () => currentSettings,
        } as Response;
      }

      if (url.includes("/budget") && method === "PUT") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        putRequests.push({ url, body });
        currentBudget.target = body.target;
        return {
          ok: true,
          json: async () => ({ ok: true }),
        } as Response;
      }

      if (url.includes("/budget") && method === "GET") {
        return {
          ok: true,
          json: async () => currentBudget,
        } as Response;
      }

      if (url.includes("/items")) {
        return {
          ok: true,
          json: async () => [{ id: 1, name: "Olive Oil" }],
        } as Response;
      }

      if (url.includes("/recipes")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/plan")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/inventory")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });

    render(<App />);

    // Switch to Budget tab
    const budgetNav = screen.getByRole("button", { name: "Budget" });
    await user.click(budgetNav);

    // Verify budget summary cards display
    await waitFor(() => {
      expect(screen.getByText("$120.00")).toBeInTheDocument();
    });

    // Verify package quantity input is present in Fallback Estimate form
    expect(screen.getByLabelText(/Estimate package quantity/i)).toBeInTheDocument();

    // Update target budget to 150
    const targetInput = screen.getByLabelText(/Weekly Target/i);
    await user.clear(targetInput);
    await user.type(targetInput, "150");

    const setBudgetBtn = screen.getByRole("button", { name: /Set Budget/i });
    await user.click(setBudgetBtn);

    // Verify PUT /budget was called
    await waitFor(() => {
      const budgetCall = putRequests.find((r) => r.url.includes("/budget"));
      expect(budgetCall).toBeDefined();
      expect(budgetCall?.body.target).toBe(150);
    });

    // Switch to Settings tab
    const settingsNav = screen.getByRole("button", { name: "Settings" });
    await user.click(settingsNav);

    // Verify Settings view loaded
    await waitFor(() => {
      expect(screen.getByDisplayValue("2")).toBeInTheDocument();
    });

    const householdInput = screen.getByLabelText(/Household Size/i);
    await user.clear(householdInput);
    await user.type(householdInput, "4");

    const mealsInput = screen.getByLabelText(/Meals Per Week/i);
    await user.clear(mealsInput);
    await user.type(mealsInput, "6");

    // Toggle Saturday on
    const satBtn = screen.getByRole("button", { name: /Sat/i });
    await user.click(satBtn);

    // Click Save Settings
    const saveSettingsBtn = screen.getByRole("button", { name: /Save Settings/i });
    await user.click(saveSettingsBtn);

    // Verify PUT /settings calls
    await waitFor(() => {
      const settingsCalls = putRequests.filter((r) => r.url.includes("/settings"));
      expect(settingsCalls.length).toBeGreaterThan(0);
      const keys = settingsCalls.map((c) => c.body.key);
      expect(keys).toContain("household_size");
      expect(keys).toContain("meals_per_week");
      expect(keys).toContain("preferred_days");
    });
  });
});
