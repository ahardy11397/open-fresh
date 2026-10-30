# Receipt Ingestion Design

## Overview
Adds receipt ingestion to the openfresh Kitchen surface, enabling users to:
1. Upload digital receipt PDFs (e.g., Walmart order printouts / e-receipts) or capture/upload receipt photos from mobile cameras.
2. Automatically parse line items (name, quantity, unit, price), store, date, and total.
3. Review and edit items in an interactive modal with smart location heuristics (`pantry`, `fridge`, `freezer`).
4. Commit confirmed items in a single transaction:
   - Add items and quantities to kitchen inventory (`source="receipt"`).
   - Update the household price library (`prices_own`, `source="receipt"`).
   - Record total or line-item spend to the weekly budget (`spend`, `source="receipt"`).

---

## 1. Architecture & Processing Pipeline

### 1.1 Ingestion Flow
```
User Uploads File (.pdf, .png, .jpg, .jpeg)
        │
        ├──> PDF? ──> Extract text with pypdf
        │               │
        │               ├──> Has text layer? ──> Feed to Structured Parser
        │               └──> Scanned PDF?    ──> Render to image ──> Tesseract OCR ──> Structured Parser
        │
        └──> Image? ──> Image preprocessing (grayscale/contrast) ──> Tesseract OCR ──> Structured Parser
                                                                                              │
                                  ┌───────────────────────────────────────────────────────────┘
                                  ▼
                     Structured Parser Pipeline:
                     Step 1: Walmart Regex / Pattern Matcher (Fast, Deterministic)
                             - Extracts items, prices, quantities, date, total
                             - Sub-second execution for printed/digital PDFs
                             - If valid items found with high confidence: return
                     Step 2: Ollama LLM Fallback (gemma3n:e4b)
                             - Used when regex yields no clean items or high OCR noise
                             - Chat completions with structured JSON schema prompt
                                  │
                                  ▼
                     Database Enrichment:
                     - Match existing item names / aliases
                     - Suggest location:
                         * Previous location in kitchen inventory if known
                         * Fallback keyword heuristics:
                             Dairy / Produce / Meat / Beverage -> fridge
                             Frozen / Ice Cream -> freezer
                             Other / Dry goods -> pantry
                                  │
                                  ▼
                     Return JSON to Frontend Review Modal
```

### 1.2 System Dependencies & Python Libraries
- Python dependencies in `backend/pyproject.toml`:
  - `pypdf`: Pure Python library for PDF text extraction.
  - `pytesseract`: Python wrapper for Google Tesseract OCR.
  - `pillow`: Image processing for OCR contrast/resizing.
  - `pdf2image`: Fallback for scanned image-only PDFs.
- System dependencies:
  - `tesseract-ocr` installed in backend container (`python:3.12-slim`).

---

## 2. API Specifications

### 2.1 Parse Receipt
* **Method**: `POST`
* **Path**: `/receipts/parse`
* **Content-Type**: `multipart/form-data`
* **Form Fields**:
  - `file`: Uploaded file binary (accepts `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`).
* **Response (200 OK)**:
  ```json
  {
    "store": "Walmart",
    "date": "2026-10-30",
    "total": 42.15,
    "currency": "USD",
    "items": [
      {
        "raw_name": "GV 2% RED MILK 1 GAL",
        "name": "2% Reduced Fat Milk",
        "matched_item_id": 14,
        "suggested_location": "fridge",
        "quantity": 1.0,
        "unit": "gal",
        "price": 3.48,
        "category": "Dairy",
        "include": true
      }
    ]
  }
  ```

### 2.2 Commit Receipt
* **Method**: `POST`
* **Path**: `/receipts/commit`
* **Content-Type**: `application/json`
* **Request Body**:
  ```json
  {
    "date": "2026-10-30",
    "currency": "USD",
    "record_spend": true,
    "total_spend": 42.15,
    "items": [
      {
        "name": "2% Reduced Fat Milk",
        "category": "Dairy",
        "location": "fridge",
        "quantity": 1.0,
        "unit": "gal",
        "price": 3.48,
        "include_inventory": true,
        "include_price": true
      }
    ]
  }
  ```
* **Execution**:
  - Executes atomically within a database transaction:
    1. For each item where `include_inventory == true`:
       - Resolve or create item via `items.get_or_create(conn, name, category)`.
       - Add to inventory via `inventory.add_item(conn, item_id, location, quantity, unit, source="receipt")`.
    2. For each item where `include_price == true`:
       - Resolve or create item.
       - Record price via `pricing.record_own_price(conn, item_id, price, currency, date, package_quantity=quantity, package_unit=unit, source="receipt")`.
    3. If `record_spend == true` and `total_spend > 0`:
       - Record spend via `budget.record_spend(conn, item_id=None, price=total_spend, currency=currency, date=date, source="receipt")`.
* **Response (200 OK)**:
  ```json
  {
    "status": "ok",
    "inventory_items_added": 1,
    "prices_updated": 1,
    "spend_recorded": 42.15
  }
  ```

---

## 3. Frontend & Mobile UX

### 3.1 Kitchen View Integration
- **Upload Button**: An "Ingest Receipt" button placed in the Kitchen view header alongside tabs.
- **Hidden Input**:
  ```html
  <input type="file" accept="image/*,application/pdf" capture="environment" />
  ```
  Triggers camera snap or photo library on mobile devices, or file dialog on desktop.
- **Dropzone**: Desktop dragging of PDF/images directly onto the Kitchen inventory view.

### 3.2 Review Modal (`ReceiptReviewModal.tsx`)
- Displays extracted store name, date, total spend, and currency.
- Editable receipt-level toggle: `[x] Log spend to weekly budget`.
- Responsive table / list for extracted items:
  - Checkbox to toggle inclusion (defaults to true for groceries, user can uncheck non-groceries).
  - Item name input (pre-cleaned from raw OCR text, editable).
  - Location selector: Segmented control (`Pantry`, `Fridge`, `Freezer`) pre-populated from smart defaults.
  - Quantity & Unit inputs: Editable number stepper and unit text.
  - Price input: Line-item price.
  - Remove item button (`×`) and "Add Line Item" button to manually add missed products.
- Loading indicator during OCR and LLM parsing with friendly feedback.
- Confirm button: "Add to Kitchen" with summary toast notification upon completion.

---

## 4. Testing & Verification Plan

### 4.1 Backend Tests (`backend/tests/test_receipts.py`)
- Unit test Walmart PDF text parsing with sample digital receipt text.
- Unit test image OCR parser mock/real.
- Unit test Ollama JSON fallback parser.
- Unit test `POST /receipts/parse` endpoint.
- Unit test `POST /receipts/commit` verifying:
  - Inventory rows updated with `source="receipt"` in `inventory_events`.
  - `prices_own` rows inserted with correct `package_quantity`, `package_unit`, and `source="receipt"`.
  - `spend` recorded with correct date and total.
  - Transaction rollbacks on failure.

### 4.2 Frontend Tests (`frontend/src/__tests__/ReceiptReviewModal.test.tsx`)
- Renders review modal with parsed items.
- Allows editing name, quantity, unit, price, and location.
- Excludes unchecked items from commit payload.
- Calls API client `commitReceipt` and triggers inventory reload.
