"""
QA sweep — Menus, Shopping, Prep, Budget edge cases.

Covers gaps not in existing feature test files:
  - Non-host forbidden on all write operations
  - 404 on unknown resource IDs
  - Field validation (min/max length, numeric bounds)
  - Optional fields (assigned_to, quantity, unit, notes, paid_by)
  - Budget math (host_remaining, participant_target, multiple entries)
  - Shopping: update name and quantity
  - Prep: sort_order, completion toggle
  - Menus: all dish categories, servings field
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

PASSWORD = "SecurePass1!"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _register_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _setup(client: AsyncClient, email: str) -> tuple[str, str]:
    """Register, login, create gathering. Returns (token, gathering_id)."""
    token = await _register_login(client, email)
    resp = await client.post(
        "/api/v1/gatherings",
        json={"name": "QA Gathering", "event_date": "2026-12-01T19:00:00Z"},
        headers=_auth(token),
    )
    return token, resp.json()["id"]


# ---------------------------------------------------------------------------
# Menus — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_menu_non_host_forbidden(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m1@test.com")
    other = await _register_login(client, "qa_m1b@test.com")

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Salad", "category": "starter"},
        headers=_auth(other),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_menu_dish_not_found(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m2@test.com")
    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/menu/dishes/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_menu_all_dish_categories(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m3@test.com")
    categories = ["starter", "main", "side", "dessert", "drink", "other"]
    for cat in categories:
        resp = await client.post(
            f"/api/v1/gatherings/{gid}/menu/dishes",
            json={"name": f"Dish {cat}", "category": cat},
            headers=_auth(token),
        )
        assert resp.status_code == 201, f"Failed for category {cat}: {resp.text}"
        assert resp.json()["category"] == cat


@pytest.mark.asyncio
async def test_menu_invalid_category_rejected(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m4@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Bad Dish", "category": "snack"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_menu_dish_servings_stored(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m5@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Pasta", "category": "main", "servings": 8},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["servings"] == 8


@pytest.mark.asyncio
async def test_menu_dish_assigned_to_stored(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m6@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Wine", "category": "drink", "assigned_to": "João"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_to"] == "João"


@pytest.mark.asyncio
async def test_menu_dish_name_too_long_rejected(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m7@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "x" * 256, "category": "main"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_menu_dish_servings_zero_rejected(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_m8@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/menu/dishes",
        json={"name": "Nothing", "category": "main", "servings": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Shopping — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shopping_non_host_forbidden(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s1@test.com")
    other = await _register_login(client, "qa_s1b@test.com")

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Milk"},
        headers=_auth(other),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_shopping_item_not_found(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s2@test.com")
    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/shopping/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_shopping_item_with_quantity_and_unit(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s3@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Flour", "quantity": 500.0, "unit": "g"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity"] == 500.0
    assert data["unit"] == "g"


@pytest.mark.asyncio
async def test_shopping_item_assigned_to(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s4@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Beer", "assigned_to": "Miguel"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_to"] == "Miguel"


@pytest.mark.asyncio
async def test_shopping_update_name(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s5@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Original"},
        headers=_auth(token),
    )
    iid = add.json()["id"]

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/shopping/{iid}",
        json={"name": "Renamed"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


@pytest.mark.asyncio
async def test_shopping_quantity_zero_rejected(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s6@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/shopping",
        json={"name": "Nothing", "quantity": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shopping_purchased_count(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_s7@test.com")

    ids = []
    for name in ["Apples", "Bread", "Cheese"]:
        r = await client.post(
            f"/api/v1/gatherings/{gid}/shopping",
            json={"name": name},
            headers=_auth(token),
        )
        ids.append(r.json()["id"])

    # Mark first two as purchased
    for iid in ids[:2]:
        await client.patch(
            f"/api/v1/gatherings/{gid}/shopping/{iid}",
            json={"is_purchased": True},
            headers=_auth(token),
        )

    resp = await client.get(f"/api/v1/gatherings/{gid}/shopping", headers=_auth(token))
    data = resp.json()
    assert data["total"] == 3
    assert data["purchased"] == 2
    assert data["remaining"] == 1


# ---------------------------------------------------------------------------
# Prep — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prep_non_host_forbidden(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_p1@test.com")
    other = await _register_login(client, "qa_p1b@test.com")

    resp = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": "Set table"},
        headers=_auth(other),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_prep_task_not_found(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_p2@test.com")
    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/prep/{uuid.uuid4()}",
        json={"title": "Ghost"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_prep_assigned_to_and_sort_order(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_p3@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": "Marinate meat", "assigned_to": "Chef", "sort_order": 5},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["assigned_to"] == "Chef"
    assert data["sort_order"] == 5


@pytest.mark.asyncio
async def test_prep_completion_toggle(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_p4@test.com")
    add = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": "Set table"},
        headers=_auth(token),
    )
    tid = add.json()["id"]
    assert add.json()["is_completed"] is False

    resp = await client.patch(
        f"/api/v1/gatherings/{gid}/prep/{tid}",
        json={"is_completed": True},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_prep_list_counts(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_p5@test.com")

    tids = []
    for title in ["Task 1", "Task 2", "Task 3"]:
        r = await client.post(
            f"/api/v1/gatherings/{gid}/prep",
            json={"title": title},
            headers=_auth(token),
        )
        tids.append(r.json()["id"])

    # Complete one
    await client.patch(
        f"/api/v1/gatherings/{gid}/prep/{tids[0]}",
        json={"is_completed": True},
        headers=_auth(token),
    )

    resp = await client.get(f"/api/v1/gatherings/{gid}/prep", headers=_auth(token))
    data = resp.json()
    assert data["total"] == 3
    assert data["completed"] == 1
    assert data["remaining"] == 2


@pytest.mark.asyncio
async def test_prep_title_empty_rejected(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_p6@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/prep",
        json={"title": ""},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Budget — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_non_host_forbidden(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b1@test.com")
    other = await _register_login(client, "qa_b1b@test.com")

    resp = await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "100.00"},
        headers=_auth(other),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_budget_entry_not_found(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b2@test.com")
    resp = await client.delete(
        f"/api/v1/gatherings/{gid}/budget/entries/{uuid.uuid4()}",
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_budget_host_remaining_math(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b3@test.com")

    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR", "host_budget_limit": "200.00"},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Wine", "amount": "45.50"},
        headers=_auth(token),
    )

    resp = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    data = resp.json()
    assert data["host_budget_limit"] == "200.00"
    assert data["total_spent"] == "45.50"
    assert data["host_remaining"] == "154.50"


@pytest.mark.asyncio
async def test_budget_no_limit_remaining_is_null(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b4@test.com")

    # Set budget with no limit
    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "EUR"},
        headers=_auth(token),
    )
    resp = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    assert resp.json()["host_remaining"] is None


@pytest.mark.asyncio
async def test_budget_entry_with_paid_by_and_notes(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b5@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={
            "description": "Groceries",
            "amount": "87.30",
            "paid_by": "Maria",
            "notes": "Supermarket receipt",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    entry = resp.json()["entries"][0]
    assert entry["paid_by"] == "Maria"
    assert entry["notes"] == "Supermarket receipt"


@pytest.mark.asyncio
async def test_budget_currency_stored(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b6@test.com")
    await client.put(
        f"/api/v1/gatherings/{gid}/budget",
        json={"currency": "GBP"},
        headers=_auth(token),
    )
    resp = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    assert resp.json()["currency"] == "GBP"


@pytest.mark.asyncio
async def test_budget_entry_amount_zero_rejected(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b7@test.com")
    resp = await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Free stuff", "amount": "0.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_budget_version_increments(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b8@test.com")

    r1 = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    v0 = r1.json()["version"]

    await client.post(
        f"/api/v1/gatherings/{gid}/budget/entries",
        json={"description": "Item", "amount": "10.00"},
        headers=_auth(token),
    )
    r2 = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    assert r2.json()["version"] == v0 + 1


@pytest.mark.asyncio
async def test_budget_multiple_entries_total(client: AsyncClient) -> None:
    token, gid = await _setup(client, "qa_b9@test.com")

    for desc, amount in [("A", "10.00"), ("B", "20.50"), ("C", "5.75")]:
        await client.post(
            f"/api/v1/gatherings/{gid}/budget/entries",
            json={"description": desc, "amount": amount},
            headers=_auth(token),
        )

    resp = await client.get(f"/api/v1/gatherings/{gid}/budget", headers=_auth(token))
    assert resp.json()["total_spent"] == "36.25"
    assert len(resp.json()["entries"]) == 3
