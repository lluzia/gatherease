"""
GatherEase i18n — backend translatable strings.

Strategy
--------
The backend is responsible for translating system messages (error responses,
status strings). User-created content (gathering names, dish titles, etc.)
is never translated — it is stored and returned as-is.

Locale resolution order per request:
  1. Accept-Language header (first supported tag wins)
  2. User's preferred_language stored in DB (set via PATCH /users/me)
  3. Fallback: "en"

Supported locales: en · pt · es

Usage
-----
    from app.core.i18n import translate, get_request_locale

    message = translate("GATHERING_NOT_FOUND", locale="pt")
    # → "Evento não encontrado."

The middleware binds the resolved locale to structlog context vars so it
is available anywhere in the request stack without passing it explicitly:

    from app.core.i18n import get_request_locale
    locale = get_request_locale()   # reads from contextvars

Flutter contract
----------------
- Every error response includes a machine-readable `code` field (e.g.
  "GATHERING_NOT_FOUND") that Flutter's ARB files also key off of.
- The `message` field is a human-readable translation for display as-is
  or as a fallback when the Flutter client hasn't loaded its own strings.
- The response carries `Content-Language: <locale>` so Flutter knows
  which locale was served.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Supported locales
# ---------------------------------------------------------------------------

SUPPORTED_LOCALES: frozenset[str] = frozenset({"en", "pt", "es"})
DEFAULT_LOCALE = "en"

# ---------------------------------------------------------------------------
# Translation catalogue
# Each key is an error code (matches AppException.code).
# Values are dicts mapping locale → translated message.
# ---------------------------------------------------------------------------

_CATALOGUE: dict[str, dict[str, str]] = {
    # ── Generic ────────────────────────────────────────────────────────────
    "INTERNAL_ERROR": {
        "en": "An unexpected error occurred.",
        "pt": "Ocorreu um erro inesperado.",
        "es": "Ocurrió un error inesperado.",
    },
    "BAD_REQUEST": {
        "en": "Invalid request.",
        "pt": "Pedido inválido.",
        "es": "Solicitud inválida.",
    },
    "VALIDATION_ERROR": {
        "en": "Request validation failed.",
        "pt": "Validação do pedido falhou.",
        "es": "La validación de la solicitud falló.",
    },
    "UNPROCESSABLE": {
        "en": "Unable to process request.",
        "pt": "Não foi possível processar o pedido.",
        "es": "No se pudo procesar la solicitud.",
    },
    # ── Auth ───────────────────────────────────────────────────────────────
    "UNAUTHORISED": {
        "en": "Authentication required.",
        "pt": "Autenticação necessária.",
        "es": "Se requiere autenticación.",
    },
    "INVALID_TOKEN": {
        "en": "Token is invalid or expired.",
        "pt": "Token inválido ou expirado.",
        "es": "El token es inválido o ha expirado.",
    },
    "TOKEN_EXPIRED": {
        "en": "Token has expired.",
        "pt": "O token expirou.",
        "es": "El token ha expirado.",
    },
    # ── Access ─────────────────────────────────────────────────────────────
    "FORBIDDEN": {
        "en": "You do not have permission to perform this action.",
        "pt": "Não tem permissão para realizar esta ação.",
        "es": "No tienes permiso para realizar esta acción.",
    },
    # ── Not found ──────────────────────────────────────────────────────────
    "NOT_FOUND": {
        "en": "Resource not found.",
        "pt": "Recurso não encontrado.",
        "es": "Recurso no encontrado.",
    },
    "USER_NOT_FOUND": {
        "en": "User not found.",
        "pt": "Usuário não encontrado.",
        "es": "Usuario no encontrado.",
    },
    "GATHERING_NOT_FOUND": {
        "en": "Gathering not found.",
        "pt": "Evento não encontrado.",
        "es": "Reunión no encontrada.",
    },
    # ── Conflict ───────────────────────────────────────────────────────────
    "CONFLICT": {
        "en": "Resource already exists.",
        "pt": "O recurso já existe.",
        "es": "El recurso ya existe.",
    },
    "EMAIL_ALREADY_REGISTERED": {
        "en": "An account with this email already exists.",
        "pt": "Já existe uma conta com este email.",
        "es": "Ya existe una cuenta con este correo electrónico.",
    },
    # ── Domain-specific ────────────────────────────────────────────────────
    "GATHERING_LIMIT_REACHED": {
        "en": "Free plan limit reached. Upgrade to Premium for unlimited gatherings.",
        "pt": "Limite do plano gratuito atingido. Atualize para Premium para encontros ilimitados.",
        "es": "Límite del plan gratuito alcanzado. Actualiza a Premium para reuniones ilimitadas.",
    },
}

# ---------------------------------------------------------------------------
# Context var — set by middleware, read by translate()
# ---------------------------------------------------------------------------

# We piggyback on structlog's contextvars (already used for request_id).
# The locale is bound under the key "locale" during each request.

_LOCALE_KEY = "locale"


def get_request_locale() -> str:
    """Return the locale bound to the current request context.

    Falls back to DEFAULT_LOCALE if called outside a request (e.g. tests,
    background tasks).
    """
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get(_LOCALE_KEY, DEFAULT_LOCALE)


def bind_locale(locale: str) -> None:
    """Bind the resolved locale to the current structlog context."""
    structlog.contextvars.bind_contextvars(**{_LOCALE_KEY: locale})


# ---------------------------------------------------------------------------
# Locale resolution
# ---------------------------------------------------------------------------


def resolve_locale(accept_language: str | None) -> str:
    """Parse Accept-Language header and return the best supported locale.

    Implements a simple first-match against supported locales, handling:
      - "pt-BR,pt;q=0.9,en;q=0.8"  → "pt"
      - "es"                         → "es"
      - "fr,de"                      → "en"  (fallback)
      - None / ""                    → "en"  (fallback)

    Quality values (q=) are respected by sorting, but we don't do full
    RFC 5646 subtag matching — we just strip the region suffix.
    """
    if not accept_language:
        return DEFAULT_LOCALE

    # Split into (tag, q) pairs, sort descending by q
    tags: list[tuple[str, float]] = []
    for part in accept_language.split(","):
        part = part.strip()
        if ";q=" in part:
            tag, q_str = part.split(";q=", 1)
            try:
                q = float(q_str)
            except ValueError:
                q = 1.0
        else:
            tag, q = part, 1.0
        tags.append((tag.strip(), q))

    tags.sort(key=lambda x: x[1], reverse=True)

    for tag, _ in tags:
        # Strip region suffix: "pt-BR" → "pt", "zh-Hant" → "zh"
        base = tag.split("-")[0].lower()
        if base in SUPPORTED_LOCALES:
            return base

    return DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


def translate(code: str, locale: str | None = None) -> str:
    """Return the translated message for an error code.

    If locale is None, reads from the current request context.
    Falls back to English if the code or locale is unknown.
    """
    if locale is None:
        locale = get_request_locale()

    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE

    entry = _CATALOGUE.get(code)
    if entry is None:
        # Unknown code — log and return the code itself as a last resort
        logger.warning("i18n_missing_code", code=code, locale=locale)
        return code

    translated = entry.get(locale)
    if translated is None:
        # Locale missing for this code — fall back to English
        logger.warning("i18n_missing_locale", code=code, locale=locale)
        return entry.get(DEFAULT_LOCALE, code)

    return translated
