import { describe, it, expect, vi, afterEach } from "vitest";
import { api } from "../api/client";
import type { ReceiptCommitPayload } from "../types";

describe("Receipt API Client", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe("parseReceipt", () => {
    it("calls POST /receipts/parse with multipart formData and without Content-Type header", async () => {
      const file = new File(["fake_pdf_content"], "receipt.pdf", {
        type: "application/pdf",
      });

      const mockResponse = {
        store: "Walmart",
        date: "2026-10-30",
        total: 25.5,
        currency: "USD",
        items: [
          {
            raw_name: "GV MILK 1GAL",
            name: "Milk",
            matched_item_id: 1,
            suggested_location: "fridge" as const,
            quantity: 1,
            unit: "gal",
            price: 3.48,
            category: "Dairy",
            include: true,
          },
        ],
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      });
      globalThis.fetch = mockFetch;

      const res = await api.parseReceipt(file);

      expect(res).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledTimes(1);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain("/receipts/parse");
      expect(init?.method).toBe("POST");
      expect(init?.body).toBeInstanceOf(FormData);
      expect((init?.body as FormData).get("file")).toBe(file);

      // Verify Content-Type was NOT set to application/json so browser sets multipart boundary
      if (init?.headers) {
        expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
      }
    });

    it("throws an error when parseReceipt request fails", async () => {
      const file = new File(["bad content"], "receipt.png", { type: "image/png" });
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({ detail: "Failed to parse receipt" }),
      });
      globalThis.fetch = mockFetch;

      await expect(api.parseReceipt(file)).rejects.toThrow("Failed to parse receipt");
    });
  });

  describe("commitReceipt", () => {
    it("calls POST /receipts/commit with json body and application/json header", async () => {
      const payload: ReceiptCommitPayload = {
        date: "2026-10-30",
        currency: "USD",
        record_spend: true,
        total_spend: 25.5,
        items: [
          {
            name: "Milk",
            category: "Dairy",
            location: "fridge",
            quantity: 1,
            unit: "gal",
            price: 3.48,
            include_inventory: true,
            include_price: true,
          },
        ],
      };

      const mockResponse = {
        status: "ok",
        inventory_items_added: 1,
        prices_updated: 1,
        spend_recorded: 25.5,
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      });
      globalThis.fetch = mockFetch;

      const res = await api.commitReceipt(payload);

      expect(res).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledTimes(1);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain("/receipts/commit");
      expect(init?.method).toBe("POST");
      expect(init?.headers).toEqual(
        expect.objectContaining({ "Content-Type": "application/json" })
      );
      expect(JSON.parse(init?.body as string)).toEqual(payload);
    });

    it("throws an error when commitReceipt request fails", async () => {
      const payload: ReceiptCommitPayload = {
        date: "2026-10-30",
        currency: "USD",
        record_spend: false,
        total_spend: 0,
        items: [],
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "Database commit failed" }),
      });
      globalThis.fetch = mockFetch;

      await expect(api.commitReceipt(payload)).rejects.toThrow("Database commit failed");
    });
  });
});
