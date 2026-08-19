"""Pluggable e-invoice (GSP/IRP) provider interface — scaffolding only.

No concrete implementation is registered in v1. Real GST e-invoicing
requires a paid GSP/IRP provider integration (API credentials, a
per-clinic sandbox, the NIC e-invoice JSON schema, digital signing) that
is out of scope for this module until a provider adapter is built and
wired in here. Every consumer of this interface (the retry endpoint,
the submission queue) must degrade honestly when no provider is
registered — never fabricate a success state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice


@dataclass
class EInvoiceResult:
    state: str  # "generated" | "rejected" | "error"
    irn: str | None = None
    ack_number: str | None = None
    ack_date: str | None = None
    signed_qr_payload: str | None = None
    error_message: str | None = None


class EInvoiceProviderClient(ABC):
    """Interface a real GSP/IRP adapter would implement.

    Deliberately unimplemented in v1 — see module docstring.
    """

    @abstractmethod
    async def submit(self, invoice: Invoice, payload: dict[str, Any]) -> EInvoiceResult: ...

    @abstractmethod
    async def check_status(self, irn: str) -> EInvoiceResult: ...


_registered_provider: EInvoiceProviderClient | None = None


def get_registered_provider() -> EInvoiceProviderClient | None:
    return _registered_provider


def register_provider(provider: EInvoiceProviderClient) -> None:  # pragma: no cover
    """Registration point for a future real adapter. Not called in v1."""
    global _registered_provider
    _registered_provider = provider
