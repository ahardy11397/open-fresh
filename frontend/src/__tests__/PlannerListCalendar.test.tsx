import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

describe("Planner, Grocery List, and Calendar surfaces", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("test_planner_renders_week_auto_populates_and_marks_cooked", async () => {
    const user = userEvent.setup();

    const planEntries = [
      {
        id: 101,
        recipe_id: 1,
        title: "Garlic Pasta",
        date: "2026-10-19",
        slot: "dinner",
        servings_override: 2,
        cooked: false,
      },
    ];

    const requestedUrls: string[] = [];
    const postRequests: { url: string; body: any }[] = [];

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      requestedUrls.push(url);
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

      if (url.includes("/recipes") && !url.includes("/ingest")) {
        return {
          ok: true,
          json: async () => [
            {
              id: 1,
              title: "Garlic Pasta",
              servings: 2,
              needs_review: false,
              ingredients: [],
            },
          ],
        } as Response;
      }

      if (url.includes("/plan/auto-populate") && method === "POST") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        postRequests.push({ url, body });
        return {
          ok: true,
          json: async () => ({ entry_ids: [102, 103] }),
        } as Response;
      }

      if (url.includes("/cooked") && method === "POST") {
        postRequests.push({ url, body: null });
        return {
          ok: true,
          json: async () => ({ ok: true }),
        } as Response;
      }

      if (url.includes("/plan") && method === "GET") {
        return {
          ok: true,
          json: async () => planEntries,
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

    // Wait for Planner to load and render the planned entry
    await waitFor(() => {
      expect(screen.getByText("Garlic Pasta")).toBeInTheDocument();
    });

    // Check meal count target progress
    expect(screen.getByText(/1 \/ 5 meals planned/i)).toBeInTheDocument();

    // Click Auto-Populate Week button
    const autoPopulateBtn = screen.getByRole("button", {
      name: /Auto-Populate/i,
    });
    await user.click(autoPopulateBtn);

    // Verify POST /plan/auto-populate was called
    await waitFor(() => {
      const autoPopCall = postRequests.find((r) =>
        r.url.includes("/plan/auto-populate")
      );
      expect(autoPopCall).toBeDefined();
      expect(autoPopCall?.body).toHaveProperty("week_start");
    });

    // Click Mark Cooked on the uncooked entry
    const markCookedBtn = screen.getByRole("button", { name: /Mark Cooked/i });
    await user.click(markCookedBtn);

    // Verify POST /plan/101/cooked was called
    await waitFor(() => {
      const cookedCall = postRequests.find((r) =>
        r.url.includes("/plan/101/cooked")
      );
      expect(cookedCall).toBeDefined();
    });
  });

  it("test_grocery_list_complete_shopping_adds_to_inventory", async () => {
    const user = userEvent.setup();

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

      if (url.includes("/list")) {
        return {
          ok: true,
          json: async () => [
            {
              item_id: 2,
              name: "garlic",
              quantity: 8,
              unit: "clove",
              price: 2.5,
              currency: "USD",
              price_source: "estimate",
            },
          ],
        } as Response;
      }

      if (url.includes("/budget")) {
        return {
          ok: true,
          json: async () => ({
            week_start: "2026-10-19",
            target: 100,
            currency: "USD",
            estimated: 2.5,
            actual: 0,
            remaining: 97.5,
          }),
        } as Response;
      }

      if (url.includes("/inventory") && method === "POST") {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        postRequests.push({ url, body });
        return {
          ok: true,
          json: async () => ({ inventory_id: 10 }),
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

    // Switch to Grocery List tab
    const groceryListTab = screen.getByRole("button", {
      name: /Grocery List/i,
    });
    await user.click(groceryListTab);

    // Verify garlic (8 clove) is rendered
    await waitFor(() => {
      expect(screen.getByText(/garlic \(8 clove\)/i)).toBeInTheDocument();
    });

    // Check off the grocery item checkbox
    const checkbox = screen.getByRole("checkbox", { name: /garlic|picked/i });
    await user.click(checkbox);
    expect(checkbox).toBeChecked();

    // Select "fridge" destination location
    const locationSelect = screen.getByRole("combobox", {
      name: /location|destination/i,
    });
    await user.selectOptions(locationSelect, "fridge");

    // Click Complete Shopping button
    const completeBtn = screen.getByRole("button", {
      name: /Complete Shopping|Add Checked to Kitchen/i,
    });
    await user.click(completeBtn);

    // Verify POST /inventory was called with exact payload
    await waitFor(() => {
      const invCall = postRequests.find((r) => r.url.endsWith("/inventory"));
      expect(invCall).toBeDefined();
      expect(invCall?.body).toEqual({
        item_id: 2,
        location: "fridge",
        quantity: 8,
        unit: "clove",
      });
    });
  });

  it("test_calendar_fetches_month_range_and_shows_cooked_status", async () => {
    const user = userEvent.setup();

    const requestedUrls: string[] = [];

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      requestedUrls.push(url);

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

      if (url.includes("/plan") && url.includes("start_date=") && url.includes("end_date=")) {
        return {
          ok: true,
          json: async () => [
            {
              id: 201,
              recipe_id: 1,
              title: "Baked Salmon",
              date: "2026-10-15",
              slot: "dinner",
              cooked: true,
            },
            {
              id: 202,
              recipe_id: 2,
              title: "Crispy Tacos",
              date: "2026-10-22",
              slot: "dinner",
              cooked: false,
            },
          ],
        } as Response;
      }

      if (url.includes("/plan")) {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }

      if (url.includes("/recipes")) {
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

    // Switch to Calendar tab
    const calendarTab = screen.getByRole("button", { name: /Calendar/i });
    await user.click(calendarTab);

    // Verify GET /plan?start_date=...&end_date=... was requested
    await waitFor(() => {
      const rangeCall = requestedUrls.find(
        (u) => u.includes("/plan") && u.includes("start_date=") && u.includes("end_date=")
      );
      expect(rangeCall).toBeDefined();
    });

    // Verify both Cooked and Planned meals render with badges
    await waitFor(() => {
      expect(screen.getByText("Baked Salmon")).toBeInTheDocument();
      expect(screen.getByText("Crispy Tacos")).toBeInTheDocument();
    });

    expect(screen.getByText(/Cooked/i)).toBeInTheDocument();
    expect(screen.getByText(/Planned/i)).toBeInTheDocument();

    // Verify month view renders full grid (>= 28 cells)
    expect(document.querySelectorAll(".calendar-cell").length).toBeGreaterThanOrEqual(28);

    // Toggle to Week View
    const weekViewBtn = screen.getByRole("button", { name: /Week View/i });
    await user.click(weekViewBtn);

    // Verify Week View renders exactly 7 days
    expect(document.querySelectorAll(".calendar-cell")).toHaveLength(7);

    // Toggle back to Month View
    const monthViewBtn = screen.getByRole("button", { name: /Month View/i });
    await user.click(monthViewBtn);
    expect(document.querySelectorAll(".calendar-cell").length).toBeGreaterThanOrEqual(28);
  });
});
