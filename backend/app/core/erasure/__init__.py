"""GDPR erasure contributor contract and registry (ADR 0038, issue #546)."""

from app.core.erasure.registry import (
    ErasureRegistryError,
    SubjectErasureRegistry,
    erasure_registry,
)
from app.core.erasure.types import ErasureContributor, ErasureCoverage

__all__ = [
    "ErasureContributor",
    "ErasureCoverage",
    "ErasureRegistryError",
    "SubjectErasureRegistry",
    "erasure_registry",
]
