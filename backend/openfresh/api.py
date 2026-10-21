"""FastAPI routes over the openfresh core.

``build_router(get_conn)`` returns an APIRouter whose every route receives a
per-request sqlite connection via the ``get_conn`` dependency (see
``app_factory``). All POST/PATCH/PUT bodies are Pydantic models; every
endpoint returns 200 on success and empty collections on empty state.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from openfresh import (
    budget,
    ingest,
    inventory,
    items,
    listgen,
    planner,
    pricing,
    recipes,
    settings,
)

# --- request models -------------------------------------------------------


class ItemCreate(BaseModel):
    name: str
    category: str | None = None


class ItemPatch(BaseModel):
    category: str | None = None


class AliasCreate(BaseModel):
    raw: str
    item_id: int


class InventoryCreate(BaseModel):
    name: str | None = None
    item_id: int | None = None
    location: Literal["pantry", "fridge", "freezer"]
    quantity: float = Field(ge=0)
    unit: str = ""


class InventoryPatch(BaseModel):
    delta: float


class RecipeCreate(BaseModel):
    title: str
    servings: int = Field(default=2, ge=1)
    source_url: str | None = None
    steps: list[str] | None = None
    total_time: str | None = None
    review_notes: str | None = None


class IngredientCreate(BaseModel):
    raw: str
    name: str | None = None
    quantity: float | None = None
    unit: str = ""
    staple: bool = False


class IngredientIn(BaseModel):
    raw: str | None = None
    name: str | None = None
    quantity: float | None = None
    unit: str = ""
    staple: bool = False

    @model_validator(mode="after")
    def validate_raw_or_name(self) -> IngredientIn:
        has_raw = bool(self.raw and self.raw.strip())
        has_name = bool(self.name and self.name.strip())
        if not has_raw and not has_name:
            raise ValueError("Either raw or name must be provided")
        return self


class RecipeIngestBody(BaseModel):
    url: str | None = None
    raw_text: str | None = None
    title: str | None = None


class RecipeReingestBody(BaseModel):
    raw_text: str


class RecipePatch(BaseModel):
    title: str | None = None
    servings: int | None = Field(default=None, ge=1)
    steps: list[str] | None = None
    total_time: str | None = None
    needs_review: bool | None = None
    review_notes: str | None = None
    ingredients: list[IngredientIn] | None = None


class PlanCreate(BaseModel):
    recipe_id: int
    date: date
    slot: str | None = None
    servings_override: int | None = None


class AutoPopulateBody(BaseModel):
    week_start: date


class OwnPriceCreate(BaseModel):
    item_id: int
    price: float
    currency: str
    date: date
    package_quantity: float = Field(default=1.0, gt=0)
    package_unit: str = ""


class EstimateCreate(BaseModel):
    item_id: int | None = None
    category: str | None = None
    price: float
    currency: str
    package_quantity: float = Field(default=1.0, gt=0)
    package_unit: str = ""


class BudgetPut(BaseModel):
    target: float
    currency: str | None = None


class SpendCreate(BaseModel):
    item_id: int | None = None
    price: float
    currency: str
    date: date


class SettingsPut(BaseModel):
    key: str
    value: str


def build_router(get_conn: Callable[[], Iterator[sqlite3.Connection]]) -> APIRouter:
    router = APIRouter()

    def current_week_start() -> str:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat()

    def ok() -> dict[str, bool]:
        return {"ok": True}

    # --- items ------------------------------------------------------------

    @router.get("/items")
    def get_items(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
        return items.list_items(conn)

    @router.post("/items")
    def post_item(
        body: ItemCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        return {"item_id": items.get_or_create(conn, body.name, body.category)}

    @router.patch("/items/{item_id}")
    def patch_item(
        item_id: int,
        body: ItemPatch,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        try:
            items.set_category(conn, item_id, body.category)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ok()

    @router.post("/items/alias")
    def post_alias(
        body: AliasCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        try:
            items.rename_alias(conn, body.raw, body.item_id)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=422, detail="item_id does not exist"
            ) from exc
        return ok()

    # --- inventory ----------------------------------------------------------

    @router.get("/inventory")
    def get_inventory(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
        return inventory.get_all(conn)

    @router.post("/inventory")
    def post_inventory(
        body: InventoryCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        if body.item_id is not None:
            item_id = body.item_id
        elif body.name is not None:
            item_id = items.get_or_create_with_alias(conn, body.name)
        else:
            raise HTTPException(status_code=422, detail="name or item_id is required")
        inv_id = inventory.add_item(
            conn, item_id, body.location, body.quantity, body.unit
        )
        return {"inventory_id": inv_id}

    @router.patch("/inventory/{inventory_id}")
    def patch_inventory(
        inventory_id: int,
        body: InventoryPatch,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        try:
            quantity = inventory.adjust(conn, inventory_id, body.delta)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"quantity": quantity}

    @router.delete("/inventory/{inventory_id}")
    def delete_inventory(
        inventory_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        inventory.remove_item(conn, inventory_id)
        return ok()

    # --- recipes ------------------------------------------------------------

    @router.get("/recipes")
    def get_recipes(
        needs_review: bool | None = None,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> list[dict]:
        return recipes.list_recipes(conn, needs_review=needs_review)

    @router.post("/recipes")
    def post_recipe(
        body: RecipeCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        return {
            "recipe_id": recipes.create_recipe(
                conn,
                body.title,
                body.servings,
                body.source_url,
                steps=body.steps,
                total_time=body.total_time,
                review_notes=body.review_notes,
            )
        }

    @router.post("/recipes/ingest")
    def post_recipe_ingest(
        body: RecipeIngestBody, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict[str, Any]:
        has_url = bool(body.url and body.url.strip())
        has_text = bool(body.raw_text and body.raw_text.strip())
        if not has_url and not has_text:
            raise HTTPException(
                status_code=422,
                detail="Either url or raw_text must be provided",
            )
        return ingest.ingest_recipe(
            conn,
            url=body.url,
            raw_text=body.raw_text,
            title=body.title,
        )

    @router.post("/recipes/{recipe_id}/reingest")
    def post_recipe_reingest(
        recipe_id: int,
        body: RecipeReingestBody,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        if not body.raw_text or not body.raw_text.strip():
            raise HTTPException(
                status_code=422,
                detail="raw_text must not be empty",
            )
        updated = ingest.reingest_recipe(conn, recipe_id, body.raw_text)
        if updated is None:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return updated

    @router.get("/recipes/{recipe_id}")
    def get_recipe(
        recipe_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        recipe = recipes.get_recipe(conn, recipe_id)
        if recipe is None:
            raise HTTPException(status_code=404, detail="recipe not found")
        return recipe

    @router.patch("/recipes/{recipe_id}")
    def patch_recipe(
        recipe_id: int,
        body: RecipePatch,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        fields = body.model_fields_set

        tt = body.total_time if "total_time" in fields else recipes._UNSET
        rn = body.review_notes if "review_notes" in fields else recipes._UNSET
        title = body.title if "title" in fields else None
        servings = body.servings if "servings" in fields else None
        steps = body.steps if "steps" in fields else None
        needs_review = body.needs_review if "needs_review" in fields else None

        ing_dicts: list[dict[str, Any]] | None = None
        if "ingredients" in fields and body.ingredients is not None:
            ing_dicts = []
            for ing in body.ingredients:
                if ing.name is None and ing.quantity is None and ing.raw:
                    parsed = ingest.parse_ingredient_line(ing.raw)
                    ing_dicts.append(parsed)
                else:
                    ing_dicts.append({
                        "raw": ing.raw or ing.name or "",
                        "name": ing.name,
                        "quantity": ing.quantity,
                        "unit": ing.unit,
                        "staple": ing.staple,
                    })

        updated = recipes.update_recipe(
            conn,
            recipe_id,
            title=title,
            servings=servings,
            steps=steps,
            total_time=tt,
            needs_review=needs_review,
            review_notes=rn,
            ingredients=ing_dicts,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return updated

    @router.post("/recipes/{recipe_id}/ingredients")
    def post_ingredient(
        recipe_id: int,
        body: IngredientCreate,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        ingredient_id = recipes.add_ingredient(
            conn,
            recipe_id,
            body.raw,
            body.quantity,
            body.unit,
            body.staple,
            item_name=body.name,
        )
        return {"ingredient_id": ingredient_id}

    @router.delete("/recipes/{recipe_id}")
    def delete_recipe(
        recipe_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        try:
            recipes.delete_recipe(conn, recipe_id)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="recipe is planned; remove plan entries first"
            ) from exc
        return ok()

    # --- plan ---------------------------------------------------------------

    @router.get("/plan")
    def get_plan(
        week_start: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> list[dict]:
        if (start_date is None) != (end_date is None):
            raise HTTPException(
                status_code=422,
                detail="Both start_date and end_date must be provided together",
            )
        if start_date is not None and end_date is not None:
            if start_date > end_date:
                raise HTTPException(
                    status_code=422,
                    detail="start_date must be <= end_date",
                )
            return planner.get_range(
                conn, start_date.isoformat(), end_date.isoformat()
            )
        return planner.get_week(
            conn, week_start.isoformat() if week_start else current_week_start()
        )

    @router.post("/plan")
    def post_plan(
        body: PlanCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        try:
            entry_id = planner.add_entry(
                conn, body.recipe_id, body.date.isoformat(), body.slot,
                body.servings_override,
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=404, detail="recipe not found"
            ) from exc
        return {"entry_id": entry_id}

    @router.delete("/plan/{entry_id}")
    def delete_plan(
        entry_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        planner.remove_entry(conn, entry_id)
        return ok()

    @router.post("/plan/{entry_id}/cooked")
    def post_cooked(
        entry_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        planner.mark_cooked(conn, entry_id)
        return ok()

    @router.post("/plan/auto-populate")
    def post_auto_populate(
        body: AutoPopulateBody, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        return {"entry_ids": planner.auto_populate(conn, body.week_start.isoformat())}

    # --- grocery list ---------------------------------------------------------

    @router.get("/list")
    def get_list(
        week_start: date | None = None,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> list[dict]:
        return listgen.generate_list(
            conn, week_start.isoformat() if week_start else current_week_start()
        )

    # --- prices ---------------------------------------------------------------

    @router.post("/prices/own")
    def post_own_price(
        body: OwnPriceCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        try:
            pricing.record_own_price(
                conn,
                body.item_id,
                body.price,
                body.currency,
                body.date.isoformat(),
                package_quantity=body.package_quantity,
                package_unit=body.package_unit,
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=422, detail="item_id does not exist"
            ) from exc
        return ok()

    @router.post("/prices/estimate")
    def post_estimate(
        body: EstimateCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        pricing.set_estimate(
            conn,
            body.item_id,
            body.category,
            body.price,
            body.currency,
            package_quantity=body.package_quantity,
            package_unit=body.package_unit,
        )
        return ok()

    @router.get("/prices/resolve")
    def get_price_resolve(
        name: str = Query(...),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        item_id = items.get_or_create_with_alias(conn, name)
        resolved = pricing.price_item(conn, item_id)
        price, price_source, price_currency = (
            (None, None, None) if resolved is None else resolved
        )
        return {
            "item_id": item_id,
            "price": price,
            "price_source": price_source,
            "currency": price_currency,
        }

    # --- budget ---------------------------------------------------------------

    @router.get("/budget/{week_start}")
    def get_budget(
        week_start: date, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        return budget.week_summary(conn, week_start.isoformat())

    @router.put("/budget/{week_start}")
    def put_budget(
        week_start: date,
        body: BudgetPut,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        week = week_start.isoformat()
        existing = conn.execute(
            "SELECT currency FROM budgets WHERE week_start = ?", (week,)
        ).fetchone()
        if body.currency is not None:
            currency = body.currency
        elif existing is not None:
            # Updating the target alone must not reset the stored currency.
            currency = existing["currency"]
        else:
            currency = "USD"
        budget.set_budget(conn, week, body.target, currency)
        return ok()

    @router.post("/budget/{week_start}/spend")
    def post_spend(
        week_start: date,
        body: SpendCreate,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        # Refuse mixed-currency spend within one week (blind sums are wrong).
        start = body.date - timedelta(days=body.date.weekday())
        end = start + timedelta(days=7)
        rows = conn.execute(
            "SELECT DISTINCT currency FROM spend WHERE date >= ? AND date < ?",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        currencies = {row["currency"] for row in rows}
        if currencies and currencies != {body.currency}:
            raise HTTPException(
                status_code=422,
                detail=f"week {start.isoformat()} already has spend in "
                f"{', '.join(sorted(currencies))}",
            )
        budget.record_spend(
            conn, body.item_id, body.price, body.currency, body.date.isoformat()
        )
        return ok()

    # --- settings -------------------------------------------------------------

    @router.get("/settings")
    def get_settings(
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {
            "household_size": settings.get_household_size(conn),
            "meals_per_week": settings.get_positive_int(
                conn, planner.MEALS_PER_WEEK_KEY, planner.MEALS_PER_WEEK_DEFAULT
            ),
            "preferred_days": settings.get_setting(
                conn, planner.PREFERRED_DAYS_KEY, planner.PREFERRED_DAYS_DEFAULT
            ),
        }

    @router.put("/settings")
    def put_settings(
        body: SettingsPut, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        # Validate on write so garbage values can never 500 the getters.
        known_keys = {
            settings.HOUSEHOLD_SIZE_KEY,
            planner.MEALS_PER_WEEK_KEY,
            planner.PREFERRED_DAYS_KEY,
        }
        if body.key not in known_keys:
            raise HTTPException(
                status_code=422,
                detail=f"unknown setting key; known keys: {sorted(known_keys)}",
            )
        if body.key in (settings.HOUSEHOLD_SIZE_KEY, planner.MEALS_PER_WEEK_KEY):
            try:
                parsed = int(body.value)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"{body.key} must be an integer >= 1",
                ) from exc
            if parsed < 1:
                raise HTTPException(
                    status_code=422,
                    detail=f"{body.key} must be an integer >= 1",
                )
        settings.set_setting(conn, body.key, body.value)
        return ok()

    return router
