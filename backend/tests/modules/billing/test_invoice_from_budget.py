"""Invoices created from an accepted quote carry its discounts (issue #167).

The quote's line discount and its prorated global discount are folded into
each invoice line (ex-tax); Verifactu derives BaseImponible per line, so an
invoice-level discount is never an option.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _accepted_budget(
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
    *,
    quantity: int = 1,
    line_discount: dict | None = None,
    global_discount: dict | None = None,
) -> tuple[str, str]:
    """Create → add one 100 € line → accept. Returns (budget_id, item_id)."""
    r = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": setup["patient_id"],
            "valid_from": "2024-01-01",
            **(global_discount or {}),
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    budget_id = r.json()["data"]["id"]
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": setup["catalog_item_id"],
            "quantity": quantity,
            **(line_discount or {}),
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["data"]["id"]
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Test", "relationship_to_patient": "patient"}},
    )
    assert r.status_code == 200, r.text
    return budget_id, item_id


async def _invoice_from_budget(
    client: AsyncClient,
    auth_headers: dict,
    budget_id: str,
    item_id: str,
    quantity: int | None = None,
) -> dict:
    spec: dict = {"budget_item_id": item_id}
    if quantity is not None:
        spec["quantity"] = quantity
    r = await client.post(
        f"/api/v1/billing/invoices/from-budget/{budget_id}",
        json={"items": [spec]},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    invoice_id = r.json()["data"]["id"]
    r = await client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_line_and_global_discounts_reach_the_invoice(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """100 → 80 (line 20%) → 72 (global 10%): stored as one absolute line discount of 28."""
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        line_discount={"discount_type": "percentage", "discount_value": 20},
        global_discount={"global_discount_type": "percentage", "global_discount_value": 10},
    )
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert line["discount_type"] == "absolute"
    assert Decimal(line["discount_value"]) == Decimal("28.00")
    assert Decimal(line["line_discount"]) == Decimal("28.00")
    assert Decimal(line["line_total"]) == Decimal("72.00")
    assert Decimal(invoice["total"]) == Decimal("72.00")


@pytest.mark.asyncio
async def test_percentage_only_line_discount_is_kept_as_percentage(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        line_discount={"discount_type": "percentage", "discount_value": 20},
    )
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert line["discount_type"] == "percentage"
    assert Decimal(line["discount_value"]) == Decimal("20.00")
    assert Decimal(invoice["total"]) == Decimal("80.00")


@pytest.mark.asyncio
async def test_absolute_line_discount_prorated_on_partial_invoicing(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """Qty 2 with 30 € absolute discount, invoiced 1 unit → 15 € on that invoice, not 30."""
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        quantity=2,
        line_discount={"discount_type": "absolute", "discount_value": 30},
    )
    first = await _invoice_from_budget(client, auth_headers, budget_id, item_id, quantity=1)
    assert Decimal(first["items"][0]["discount_value"]) == Decimal("15.00")
    assert Decimal(first["total"]) == Decimal("85.00")
    second = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    assert Decimal(second["total"]) == Decimal("85.00")


@pytest.mark.asyncio
async def test_absolute_global_discount_is_prorated_and_never_negative(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """A global absolute discount larger than the quote is clamped: the line ends at 0, not below."""
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        global_discount={"global_discount_type": "absolute", "global_discount_value": 500},
    )
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert Decimal(line["line_discount"]) == Decimal("100.00")
    assert Decimal(line["line_total"]) == Decimal("0.00")
    assert Decimal(invoice["total"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_no_discount_round_trips_untouched(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    budget_id, item_id = await _accepted_budget(client, auth_headers, budget_clinic_setup)
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert line["discount_type"] is None
    assert Decimal(invoice["total"]) == Decimal("100.00")


async def _invoiced_qty(client: AsyncClient, auth_headers: dict, budget_id: str) -> int:
    r = await client.get(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["items"][0]["invoiced_quantity"]


@pytest.mark.asyncio
async def test_void_delete_and_item_edits_release_quote_lines(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """invoiced_quantity follows the live invoice lines (issue #175)."""
    budget_id, item_id = await _accepted_budget(
        client, auth_headers, budget_clinic_setup, quantity=3
    )
    h = auth_headers
    b = "/api/v1/billing/invoices"

    # Void a draft → line comes back.
    inv = await _invoice_from_budget(client, h, budget_id, item_id, quantity=2)
    assert await _invoiced_qty(client, h, budget_id) == 2
    r = await client.post(f"{b}/{inv['id']}/void", headers=h)
    assert r.status_code == 200, r.text
    assert await _invoiced_qty(client, h, budget_id) == 0

    # Delete a draft → line comes back.
    inv = await _invoice_from_budget(client, h, budget_id, item_id, quantity=2)
    r = await client.delete(f"{b}/{inv['id']}", headers=h)
    assert r.status_code == 204, r.text
    assert await _invoiced_qty(client, h, budget_id) == 0

    # Editing / deleting a draft line keeps the counter in sync.
    inv = await _invoice_from_budget(client, h, budget_id, item_id, quantity=3)
    line_id = inv["items"][0]["id"]
    r = await client.put(f"{b}/{inv['id']}/items/{line_id}", json={"quantity": 1}, headers=h)
    assert r.status_code == 200, r.text
    assert await _invoiced_qty(client, h, budget_id) == 1
    r = await client.delete(f"{b}/{inv['id']}/items/{line_id}", headers=h)
    assert r.status_code == 204, r.text
    assert await _invoiced_qty(client, h, budget_id) == 0

    # The full quantity is available again.
    await _invoice_from_budget(client, h, budget_id, item_id, quantity=3)
    assert await _invoiced_qty(client, h, budget_id) == 3
    r = await client.post(
        f"{b}/from-budget/{budget_id}", json={"items": [{"budget_item_id": item_id}]}, headers=h
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_credit_note_releases_quote_lines(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    budget_id, item_id = await _accepted_budget(
        client, auth_headers, budget_clinic_setup, quantity=2
    )
    h = auth_headers
    b = "/api/v1/billing/invoices"

    r = await client.put(
        f"/api/v1/patients/{budget_clinic_setup['patient_id']}",
        json={"billing_tax_id": "12345678Z"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    for prefix, series_type in (("FAC", "invoice"), ("RECT", "credit_note")):
        r = await client.post(
            "/api/v1/billing/series",
            json={"prefix": prefix, "series_type": series_type, "is_default": True},
            headers=h,
        )
        assert r.status_code == 201, r.text

    inv = await _invoice_from_budget(client, h, budget_id, item_id)
    r = await client.post(f"{b}/{inv['id']}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text
    assert await _invoiced_qty(client, h, budget_id) == 2

    r = await client.post(f"{b}/{inv['id']}/credit-note", json={"reason": "error"}, headers=h)
    assert r.status_code == 201, r.text
    cn_id = r.json()["data"]["id"]
    assert await _invoiced_qty(client, h, budget_id) == 0

    # Dropping the draft credit note consumes the lines again.
    r = await client.delete(f"{b}/{cn_id}", headers=h)
    assert r.status_code == 204, r.text
    assert await _invoiced_qty(client, h, budget_id) == 2
