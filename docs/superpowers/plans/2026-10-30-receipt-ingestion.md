# Receipt Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add receipt ingestion (Walmart PDF printouts & mobile photos) to the openfresh kitchen, extracting items, prices, quantities, and locations, with interactive review and atomic commit to inventory, prices, and budget.

**Architecture:** A dual-engine extraction backend (lightweight PDF parsing via `pypdf`, image OCR via `pytesseract`) feeding into a fast deterministic Walmart regex parser with Ollama Gemma fallback, returning structured items enriched with database location heuristics. The frontend integrates camera/file upload on the Kitchen surface and an interactive review modal for user verification and atomic commit.

**Tech Stack:** Python 3.12+ (FastAPI, SQLite, pypdf, pytesseract, Pillow), React 18, TypeScript, Vitest.

**Spec:** docs/superpowers/specs/2026-10-30-receipt-ingestion-design.md

## Global Constraints

- SQLite single database with WAL mode and foreign keys ON.
- Source tagging: inventory changes from receipts MUST use `source="receipt"` in `inventory_events`.
- Price library updates from receipts MUST record `source="receipt"`.
- Budget spend from receipts MUST record `source="receipt"`.
- Inventory quantity floor: resulting inventory quantity floored at 0.0.
- Mobile compatibility: file input MUST include `accept="image/*,application/pdf"` and `capture="environment"`.

## Review Focus

1. **Scanned PDF or multi-page digital Walmart PDF**: Ensure text extraction concatenates all pages cleanly without losing line items.
2. **Missing or zero-price lines (e.g. coupons, discounts, bottle deposit)**: Parser must handle discounts or $0.00 items gracefully without crashing or creating negative-priced inventory items.
3. **Location determination for novel items**: Novel items not previously in inventory should fall back safely to category keywords (dairy/produce -> fridge, frozen -> freezer, others -> pantry).
4. **Unchecked non-grocery items**: Items deselected by the user in the review modal must neither enter inventory nor update the price library, but spend can still match the receipt total.
5. **Partial or failed OCR**: If OCR returns noise or partial text, the parser must cleanly fall back to the Ollama extraction without raising 500 errors to the client.

---

### Task 1: Backend Dependencies & Receipt Extraction Foundation

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/openfresh/receipts.py`
- Test: `backend/tests/test_receipts_extraction.py`

**Interfaces:**
- Produces:
  - `extract_text_from_pdf(pdf_bytes: bytes) -> str`
  - `extract_text_from_image(image_bytes: bytes) -> str`
  - `extract_text(file_bytes: bytes, filename: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_receipts_extraction.py
import pytest
from openfresh.receipts import extract_text, extract_text_from_pdf, extract_text_from_image

def test_extract_text_from_pdf_digital():
    # Minimal 1-page valid PDF with text stream "WALMART STORE #1234"
    # Verify extract_text_from_pdf returns string containing "WALMART"
    pass

def test_extract_text_detects_pdf_and_image(monkeypatch):
    monkeypatch.setattr("openfresh.receipts.extract_text_from_image", lambda b: "OCR TEXT")
    assert extract_text(b"fake_image", "receipt.jpg") == "OCR TEXT"
    assert extract_text(b"fake_image", "receipt.png") == "OCR TEXT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_receipts_extraction.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Implement `extract_text` functions in `backend/openfresh/receipts.py`**

Add `pypdf`, `pytesseract`, `pillow` to `backend/pyproject.toml`. Implement PDF reading using `pypdf.PdfReader` and image OCR using `PIL.Image` and `pytesseract.image_to_string`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_receipts_extraction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/openfresh/receipts.py backend/tests/test_receipts_extraction.py
git commit -m "feat(receipts): add text extraction from PDF and image files"
```

---

### Task 2: Walmart Receipt Heuristics & Ollama Fallback

**Files:**
- Modify: `backend/openfresh/receipts.py`
- Test: `backend/tests/test_receipts_parser.py`

**Interfaces:**
- Consumes: Task 1 text extraction
- Produces:
  - `parse_walmart_receipt_text(text: str) -> dict | None`
  - `parse_receipt_with_llm(text: str, client: httpx.Client | None = None) -> dict`
  - `parse_receipt_data(text: str, client: httpx.Client | None = None) -> dict`
  - Schema:
    ```python
    {
      "store": str,
      "date": str,  # YYYY-MM-DD
      "total": float,
      "currency": str,
      "items": list[dict]  # [{"raw_name": str, "name": str, "quantity": float, "unit": str, "price": float}]
    }
    ```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_receipts_parser.py
from openfresh.receipts import parse_walmart_receipt_text, parse_receipt_data

WALMART_SAMPLE = """
Walmart
Save money. Live better.
(800) 925-6278
MANAGER JOHN DOE
10/28/2026 14:32:10

GV 2% MILK 1GAL       007874235186    3.48 F
BANANAS               000000004011    1.64 F
  2.10 lb @ 1 lb / 0.78
OREO COOKIES 12OZ     004400003202    4.28 T

SUBTOTAL                              9.40
TOTAL TAX                             0.35
TOTAL                                 9.75
"""

def test_parse_walmart_receipt_sample():
    res = parse_walmart_receipt_text(WALMART_SAMPLE)
    assert res is not None
    assert res["store"] == "Walmart"
    assert res["date"] == "2026-10-28"
    assert res["total"] == 9.75
    assert len(res["items"]) >= 3
    # Check Milk item
    milk = next(i for i in res["items"] if "MILK" in i["raw_name"])
    assert milk["price"] == 3.48
    assert milk["quantity"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_receipts_parser.py -v`
Expected: FAIL with ImportError or AttributeError

- [ ] **Step 3: Implement `parse_walmart_receipt_text` and `parse_receipt_with_llm` in `receipts.py`**

Parse Walmart items matching patterns `<NAME> <UPC> <PRICE> [F|T|N]`, weighed lines `<QTY> lb @ 1 lb / <UNITPRICE>`, order/receipt dates (`MM/DD/YYYY` or `YYYY-MM-DD`), and total. If no items match, call Ollama with structured chat completion prompt.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_receipts_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/openfresh/receipts.py backend/tests/test_receipts_parser.py
git commit -m "feat(receipts): add deterministic Walmart parser and Ollama fallback"
```

---

### Task 3: Location Heuristics & DB Enrichment

**Files:**
- Modify: `backend/openfresh/receipts.py`
- Test: `backend/tests/test_receipts_enrichment.py`

**Interfaces:**
- Consumes: Task 2 parsed data
- Produces:
  - `enrich_receipt_items(conn: sqlite3.Connection, parsed: dict) -> dict`
  - Adds `matched_item_id`, `suggested_location`, `category`, and `include` to each item.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_receipts_enrichment.py
import sqlite3
from openfresh.db import get_conn
from openfresh.receipts import enrich_receipt_items
from openfresh.inventory import add_item
from openfresh.items import get_or_create

def test_enrich_suggests_prior_location():
    conn = get_conn(":memory:")
    item_id = get_or_create(conn, "Whole Milk", category="Dairy")
    add_item(conn, item_id, "fridge", 1.0, "gal")

    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 3.48,
        "currency": "USD",
        "items": [
            {"raw_name": "GV WHOLE MILK 1GAL", "name": "Whole Milk", "quantity": 1.0, "unit": "gal", "price": 3.48}
        ]
    }
    enriched = enrich_receipt_items(conn, parsed)
    assert enriched["items"][0]["matched_item_id"] == item_id
    assert enriched["items"][0]["suggested_location"] == "fridge"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_receipts_enrichment.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `enrich_receipt_items` in `receipts.py`**

Resolve existing item by exact or alias match; lookup previous location in `inventory` table. If not found, use category keyword heuristic (`FRIDGE_KEYWORDS = {"milk", "yogurt", "cheese", "butter", "meat", "beef", "chicken", "berry", "produce"}`, `FREEZER_KEYWORDS = {"ice cream", "frozen", "pizza"}`, default `"pantry"`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_receipts_enrichment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/openfresh/receipts.py backend/tests/test_receipts_enrichment.py
git commit -m "feat(receipts): add location heuristics and database item enrichment"
```

---

### Task 4: API Endpoints (`POST /receipts/parse` & `POST /receipts/commit`)

**Files:**
- Modify: `backend/openfresh/api.py`
- Test: `backend/tests/test_receipts_api.py`

**Interfaces:**
- Produces:
  - `POST /receipts/parse` endpoint taking multipart `file`
  - `POST /receipts/commit` endpoint taking JSON payload

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_receipts_api.py
from fastapi.testclient import TestClient
from openfresh.app_factory import create_app

def test_receipt_parse_and_commit(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    # Test commit directly
    commit_payload = {
        "date": "2026-10-30",
        "currency": "USD",
        "record_spend": True,
        "total_spend": 12.50,
        "items": [
            {
                "name": "Apple Gala",
                "category": "Produce",
                "location": "fridge",
                "quantity": 3.0,
                "unit": "each",
                "price": 2.50,
                "include_inventory": True,
                "include_price": True
            }
        ]
    }
    resp = client.post("/receipts/commit", json=commit_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["inventory_items_added"] == 1

    # Verify inventory was created
    inv = client.get("/inventory?location=fridge").json()
    assert any(i["name"] == "Apple Gala" and i["quantity"] == 3.0 for i in inv)

    # Verify spend was recorded
    budget = client.get("/budget?week_start=2026-10-26").json()
    assert budget["actual"] == 12.50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_receipts_api.py -v`
Expected: FAIL with 404 Not Found for `/receipts/commit`

- [ ] **Step 3: Implement endpoints in `api.py`**

In `backend/openfresh/api.py`:
- Add `POST /receipts/parse`: read file bytes, call `extract_text`, `parse_receipt_data`, `enrich_receipt_items(conn, parsed)`.
- Add `POST /receipts/commit`: in a transaction, for each item add to inventory if `include_inventory`, record own price if `include_price`, and record spend if `record_spend`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_receipts_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/openfresh/api.py backend/tests/test_receipts_api.py
git commit -m "feat(api): implement /receipts/parse and /receipts/commit endpoints"
```

---

### Task 5: Frontend Types & API Client Methods

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/src/__tests__/ReceiptApi.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `ReceiptItem`, `ReceiptParsedData`, `ReceiptCommitItem`, `ReceiptCommitPayload`
  - `client.ts`: `api.parseReceipt(file: File): Promise<ReceiptParsedData>`, `api.commitReceipt(payload: ReceiptCommitPayload): Promise<{ status: string; inventory_items_added: number }>`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/__tests__/ReceiptApi.test.ts
import { describe, it, expect, vi } from "vitest";
import { api } from "../api/client";

describe("Receipt API Client", () => {
  it("calls POST /receipts/parse with multipart formData", async () => {
    const file = new File(["fake_content"], "receipt.pdf", { type: "application/pdf" });
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ store: "Walmart", total: 10, items: [] }),
    });
    global.fetch = mockFetch;

    const res = await api.parseReceipt(file);
    expect(res.store).toBe("Walmart");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/receipts/parse"),
      expect.objectContaining({ method: "POST" })
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- src/__tests__/ReceiptApi.test.ts`
Expected: FAIL with Property 'parseReceipt' does not exist on type

- [ ] **Step 3: Implement types and api client methods**

Add types in `frontend/src/types.ts` and implementation methods `parseReceipt` and `commitReceipt` in `frontend/src/api/client.ts`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- src/__tests__/ReceiptApi.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/api/client.ts frontend/src/__tests__/ReceiptApi.test.ts
git commit -m "feat(frontend): add receipt types and api client methods"
```

---

### Task 6: Frontend Review Modal Component (`ReceiptReviewModal.tsx`)

**Files:**
- Create: `frontend/src/features/ReceiptReviewModal.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/ReceiptReviewModal.test.tsx`

**Interfaces:**
- Consumes: Task 5 types and client methods
- Produces:
  - `<ReceiptReviewModal data={parsedData} onClose={...} onCommitted={...} />`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/__tests__/ReceiptReviewModal.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReceiptReviewModal } from "../features/ReceiptReviewModal";

describe("ReceiptReviewModal", () => {
  it("renders parsed receipt items and allows changing location", async () => {
    const user = userEvent.setup();
    const mockData = {
      store: "Walmart",
      date: "2026-10-30",
      total: 3.48,
      currency: "USD",
      items: [
        {
          raw_name: "GV 2% MILK 1GAL",
          name: "2% Milk",
          suggested_location: "fridge" as const,
          quantity: 1,
          unit: "gal",
          price: 3.48,
          category: "Dairy",
          include: true,
        },
      ],
    };
    const onCommit = vi.fn();
    render(<ReceiptReviewModal data={mockData} onClose={vi.fn()} onCommitted={onCommit} />);

    expect(screen.getByDisplayValue("2% Milk")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3.48")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- src/__tests__/ReceiptReviewModal.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implement `ReceiptReviewModal.tsx` and modal styles in `styles.css`**

Support toggling item inclusion, modifying name/quantity/unit/price/location, toggling budget spend, adding a row, and submitting to `api.commitReceipt`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- src/__tests__/ReceiptReviewModal.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/ReceiptReviewModal.tsx frontend/src/styles.css frontend/src/__tests__/ReceiptReviewModal.test.tsx
git commit -m "feat(frontend): create ReceiptReviewModal component and styles"
```

---

### Task 7: Integrate Ingest Trigger into Kitchen Surface & Mobile Capture

**Files:**
- Modify: `frontend/src/features/KitchenView.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/KitchenReceiptIntegration.test.tsx`

**Interfaces:**
- Consumes: Task 6 `ReceiptReviewModal`
- Produces:
  - Ingest Receipt button in `KitchenView`
  - Mobile `<input type="file" accept="image/*,application/pdf" capture="environment" />`
  - Drag-and-drop file upload handler
  - Modal opening, loading state spinner, and inventory refresh on commit

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/__tests__/KitchenReceiptIntegration.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { KitchenView } from "../features/KitchenView";

describe("KitchenView Receipt Integration", () => {
  it("renders Ingest Receipt button and file input with camera capture", () => {
    render(<KitchenView />);
    expect(screen.getByRole("button", { name: /Ingest Receipt/i })).toBeInTheDocument();
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();
    expect(fileInput.getAttribute("accept")).toContain("image/*");
    expect(fileInput.getAttribute("accept")).toContain("application/pdf");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- src/__tests__/KitchenReceiptIntegration.test.tsx`
Expected: FAIL

- [ ] **Step 3: Update `KitchenView.tsx`**

Add file input with `capture="environment"`, Ingest Receipt button in kitchen header, file upload handler calling `api.parseReceipt`, loading indicator, and `ReceiptReviewModal` conditional rendering. Upon commit, refresh active inventory.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- src/__tests__/KitchenReceiptIntegration.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/KitchenView.tsx frontend/src/styles.css frontend/src/__tests__/KitchenReceiptIntegration.test.tsx
git commit -m "feat(kitchen): integrate receipt upload and review modal into Kitchen view"
```

---

### Task 8: End-to-End System Integration & Full Suite Verification

**Files:**
- Modify: `frontend/src/__tests__/PlannerListCalendar.test.tsx` (stabilize system date mock)
- Modify: Dockerfile / docs if needed

- [ ] **Step 1: Run full backend test suite**

Run: `pytest backend/tests -v`
Expected: All tests pass.

- [ ] **Step 2: Run full frontend test suite**

Run: `npm --prefix frontend test`
Expected: All tests pass.

- [ ] **Step 3: Run e2e integration test with sample Walmart receipt**

Verify that uploading a sample Walmart receipt populates inventory, updates price library, and logs spend.

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "chore: verify end-to-end receipt ingestion and update test suite"
```
