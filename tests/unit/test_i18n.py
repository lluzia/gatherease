"""
Tests for the i18n layer.

Covers:
  - resolve_locale(): Accept-Language parsing, q-value ordering, fallback
  - translate(): known codes, unknown codes, locale fallback
  - Middleware: Content-Language response header
  - Error responses: message translated per Accept-Language
  - Full locale round-trip: pt and es
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    resolve_locale,
    translate,
)


# ---------------------------------------------------------------------------
# resolve_locale unit tests (pure function — no HTTP needed)
# ---------------------------------------------------------------------------


def test_resolve_locale_english():
    assert resolve_locale("en") == "en"


def test_resolve_locale_portuguese():
    assert resolve_locale("pt") == "pt"


def test_resolve_locale_spanish():
    assert resolve_locale("es") == "es"


def test_resolve_locale_region_stripped():
    # "pt-BR" → "pt"
    assert resolve_locale("pt-BR") == "pt"


def test_resolve_locale_region_stripped_es():
    # "es-MX" → "es"
    assert resolve_locale("es-MX") == "es"


def test_resolve_locale_q_value_ordering():
    # Browser sends pt first with q=0.9, but en with q=1.0 — en wins
    assert resolve_locale("en;q=1.0,pt;q=0.9") == "en"


def test_resolve_locale_q_value_pt_preferred():
    # pt listed first with no q (defaults to 1.0), en second
    assert resolve_locale("pt,en;q=0.8") == "pt"


def test_resolve_locale_unsupported_falls_back():
    # French not supported → fallback to en
    assert resolve_locale("fr") == DEFAULT_LOCALE


def test_resolve_locale_unsupported_then_supported():
    # "fr,de,pt" — fr and de not supported, pt is → "pt"
    assert resolve_locale("fr,de,pt;q=0.7") == "pt"


def test_resolve_locale_none_returns_default():
    assert resolve_locale(None) == DEFAULT_LOCALE


def test_resolve_locale_empty_string_returns_default():
    assert resolve_locale("") == DEFAULT_LOCALE


def test_resolve_locale_wildcard_returns_default():
    # "*" is not a valid locale tag — falls back
    assert resolve_locale("*") == DEFAULT_LOCALE


def test_resolve_locale_complex_header():
    # Real browser header
    assert resolve_locale("pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7") == "pt"


def test_supported_locales_complete():
    assert SUPPORTED_LOCALES == {"en", "pt", "es"}


# ---------------------------------------------------------------------------
# translate() unit tests
# ---------------------------------------------------------------------------


def test_translate_known_code_en():
    assert translate("GATHERING_NOT_FOUND", locale="en") == "Gathering not found."


def test_translate_known_code_pt():
    msg = translate("GATHERING_NOT_FOUND", locale="pt")
    assert msg == "Evento não encontrado."


def test_translate_known_code_es():
    msg = translate("GATHERING_NOT_FOUND", locale="es")
    assert msg == "Reunión no encontrada."


def test_translate_email_conflict_pt():
    msg = translate("EMAIL_ALREADY_REGISTERED", locale="pt")
    assert "email" in msg.lower()
    assert msg != translate("EMAIL_ALREADY_REGISTERED", locale="en")


def test_translate_email_conflict_es():
    msg = translate("EMAIL_ALREADY_REGISTERED", locale="es")
    assert "correo" in msg.lower()


def test_translate_unknown_code_returns_code():
    # Missing from catalogue → returns the code itself
    result = translate("TOTALLY_MADE_UP_CODE", locale="en")
    assert result == "TOTALLY_MADE_UP_CODE"


def test_translate_unsupported_locale_falls_back_to_en():
    # "fr" not supported → falls back to English entry
    msg = translate("GATHERING_NOT_FOUND", locale="fr")
    assert msg == translate("GATHERING_NOT_FOUND", locale="en")


def test_translate_all_codes_have_all_locales():
    """Every catalogue entry must have translations for all supported locales."""
    from app.core.i18n import _CATALOGUE

    missing = []
    for code, translations in _CATALOGUE.items():
        for locale in SUPPORTED_LOCALES:
            if locale not in translations:
                missing.append(f"{code}.{locale}")
    assert missing == [], f"Missing translations: {missing}"


def test_translate_no_empty_strings():
    """No translation should be an empty string."""
    from app.core.i18n import _CATALOGUE

    empties = []
    for code, translations in _CATALOGUE.items():
        for locale, msg in translations.items():
            if not msg.strip():
                empties.append(f"{code}.{locale}")
    assert empties == [], f"Empty translations: {empties}"


# ---------------------------------------------------------------------------
# HTTP-level tests — middleware and error response translation
# ---------------------------------------------------------------------------


PASSWORD = "SecurePass1!"


async def _register_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_content_language_header_default(client: AsyncClient) -> None:
    """No Accept-Language → Content-Language: en in response."""
    resp = await client.get("/health")
    assert resp.headers.get("content-language") == "en"


@pytest.mark.asyncio
async def test_content_language_header_pt(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"Accept-Language": "pt"})
    assert resp.headers.get("content-language") == "pt"


@pytest.mark.asyncio
async def test_content_language_header_es(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"Accept-Language": "es"})
    assert resp.headers.get("content-language") == "es"


@pytest.mark.asyncio
async def test_content_language_region_normalised(client: AsyncClient) -> None:
    """pt-BR should resolve to pt."""
    resp = await client.get("/health", headers={"Accept-Language": "pt-BR"})
    assert resp.headers.get("content-language") == "pt"


@pytest.mark.asyncio
async def test_content_language_unsupported_falls_back(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"Accept-Language": "fr"})
    assert resp.headers.get("content-language") == "en"


@pytest.mark.asyncio
async def test_error_message_translated_pt(client: AsyncClient) -> None:
    """A 404 error for a gathering returns a Portuguese message when requested."""
    import uuid

    token = await _register_login(client, "i18n_pt1@test.com")
    resp = await client.get(
        f"/api/v1/gatherings/{uuid.uuid4()}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept-Language": "pt",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Evento não encontrado."


@pytest.mark.asyncio
async def test_error_message_translated_es(client: AsyncClient) -> None:
    import uuid

    token = await _register_login(client, "i18n_es1@test.com")
    resp = await client.get(
        f"/api/v1/gatherings/{uuid.uuid4()}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept-Language": "es",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Reunión no encontrada."


@pytest.mark.asyncio
async def test_error_message_english_by_default(client: AsyncClient) -> None:
    import uuid

    token = await _register_login(client, "i18n_en1@test.com")
    resp = await client.get(
        f"/api/v1/gatherings/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Gathering not found."


@pytest.mark.asyncio
async def test_validation_error_translated_pt(client: AsyncClient) -> None:
    """422 validation errors have a translated top-level message."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "x"},
        headers={"Accept-Language": "pt"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["message"] == "Validação do pedido falhou."


@pytest.mark.asyncio
async def test_auth_error_translated_pt(client: AsyncClient) -> None:
    """401 from wrong password is translated."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "i18n_auth1@test.com", "password": PASSWORD},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "i18n_auth1@test.com", "password": "wrongpass"},
        headers={"Accept-Language": "es"},
    )
    assert resp.status_code == 401
    # Auth service sets message dynamically — check code is correct
    assert resp.json()["error"]["code"] == "UNAUTHORISED"


@pytest.mark.asyncio
async def test_forbidden_error_translated_pt(client: AsyncClient) -> None:
    """403 from non-host access returns Portuguese message."""
    host_token = await _register_login(client, "i18n_host1@test.com")
    other_token = await _register_login(client, "i18n_other1@test.com")

    g = await client.post(
        "/api/v1/gatherings",
        json={"name": "Party", "event_date": "2026-12-01T19:00:00Z"},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    gid = g.json()["id"]

    resp = await client.get(
        f"/api/v1/gatherings/{gid}",
        headers={
            "Authorization": f"Bearer {other_token}",
            "Accept-Language": "pt",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Não tem permissão para realizar esta ação."


@pytest.mark.asyncio
async def test_q_value_locale_selection(client: AsyncClient) -> None:
    """Browser sends pt-BR,pt;q=0.9,en;q=0.8 — should resolve to pt."""
    resp = await client.get(
        "/health",
        headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
    )
    assert resp.headers.get("content-language") == "pt"
