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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from openfresh import (
    budget,
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


class AliasCreate(BaseModel):
    raw: str
    item_id: int


class InventoryCreate(BaseModel):
    name: str | None = None
    item_id: int | None = None
    location: str
    quantity: float
    unit: str = ""


class InventoryPatch(BaseModel):
    delta: float


class RecipeCreate(BaseModel):
    title: str
    servings: int = 2
    source_url: str | None = None


class IngredientCreate(BaseModel):
    raw: str
    quantity: float | None = None
    unit: str = ""
    staple: bool = False


class PlanCreate(BaseModel):
    recipe_id: int
    date: str
    slot: str | None = None
    servings_override: int | None = None


class AutoPopulateBody(BaseModel):
    week_start: str


class OwnPriceCreate(BaseModel):
    item_id: int
    price: float
    currency: str
    date: str


class EstimateCreate(BaseModel):
    item_id: int | None = None
    category: str | None = None
    price: float
    currency: str


class BudgetPut(BaseModel):
    target: float
    currency: str = "USD"


class SpendCreate(BaseModel):
    item_id: int | None = None
    price: float
    currency: str
    date: str


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
        return {"item_id": items.get_or_create(conn, body.name)}

    @router.post("/items/alias")
    def post_alias(
        body: AliasCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        items.rename_alias(conn, body.raw, body.item_id)
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
    def get_recipes(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
        return recipes.list_recipes(conn)

    @router.post("/recipes")
    def post_recipe(
        body: RecipeCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        return {
            "recipe_id": recipes.create_recipe(
                conn, body.title, body.servings, body.source_url
            )
        }

    @router.get("/recipes/{recipe_id}")
    def get_recipe(
        recipe_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        recipe = recipes.get_recipe(conn, recipe_id)
        if recipe is None:
            raise HTTPException(status_code=404, detail="recipe not found")
        return recipe

    @router.post("/recipes/{recipe_id}/ingredients")
    def post_ingredient(
        recipe_id: int,
        body: IngredientCreate,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        ingredient_id = recipes.add_ingredient(
            conn, recipe_id, body.raw, body.quantity, body.unit, body.staple
        )
        return {"ingredient_id": ingredient_id}

    @router.delete("/recipes/{recipe_id}")
    def delete_recipe(
        recipe_id: int, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        recipes.delete_recipe(conn, recipe_id)
        return ok()

    # --- plan ---------------------------------------------------------------

    @router.get("/plan")
    def get_plan(
        week_start: str | None = None,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> list[dict]:
        return planner.get_week(conn, week_start or current_week_start())

    @router.post("/plan")
    def post_plan(
        body: PlanCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        entry_id = planner.add_entry(
            conn, body.recipe_id, body.date, body.slot, body.servings_override
        )
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
        return {"entry_ids": planner.auto_populate(conn, body.week_start)}

    # --- grocery list ---------------------------------------------------------

    @router.get("/list")
    def get_list(
        week_start: str | None = None,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> list[dict]:
        return listgen.generate_list(conn, week_start or current_week_start())

    # --- prices ---------------------------------------------------------------

    @router.post("/prices/own")
    def post_own_price(
        body: OwnPriceCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        pricing.record_own_price(
            conn, body.item_id, body.price, body.currency, body.date
        )
        return ok()

    @router.post("/prices/estimate")
    def post_estimate(
        body: EstimateCreate, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        pricing.set_estimate(
            conn, body.item_id, body.category, body.price, body.currency
        )
        return ok()

    @router.get("/prices/resolve")
    def get_price_resolve(
        name: str = Query(...),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        item_id = items.get_or_create_with_alias(conn, name)
        resolved = pricing.price_item(conn, item_id)
        price, price_source = (None, None) if resolved is None else resolved
        return {
            "item_id": item_id,
            "price": price,
            "price_source": price_source,
        }

    # --- budget ---------------------------------------------------------------

    @router.get("/budget/{week_start}")
    def get_budget(
        week_start: str, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        return budget.week_summary(conn, week_start)

    @router.put("/budget/{week_start}")
    def put_budget(
        week_start: str,
        body: BudgetPut,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        budget.set_budget(conn, week_start, body.target, body.currency)
        return ok()

    @router.post("/budget/{week_start}/spend")
    def post_spend(
        week_start: str,
        body: SpendCreate,
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict:
        budget.record_spend(
            conn, body.item_id, body.price, body.currency, body.date
        )
        return ok()

    # --- settings -------------------------------------------------------------

    @router.get("/settings")
    def get_settings(
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {
            "household_size": settings.get_household_size(conn),
            "meals_per_week": int(
                settings.get_setting(
                    conn, planner.MEALS_PER_WEEK_KEY, planner.MEALS_PER_WEEK_DEFAULT
                )
            ),
            "preferred_days": settings.get_setting(
                conn, planner.PREFERRED_DAYS_KEY, planner.PREFERRED_DAYS_DEFAULT
            ),
        }

    @router.put("/settings")
    def put_settings(
        body: SettingsPut, conn: sqlite3.Connection = Depends(get_conn)
    ) -> dict:
        settings.set_setting(conn, body.key, body.value)
        return ok()

    return router
