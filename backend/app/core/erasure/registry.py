"""Registry of GDPR erasure contributors (ADR 0038, issue #546)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.erasure.types import ErasureContributor

if TYPE_CHECKING:
    from app.core.plugins.base import BaseModule

logger = logging.getLogger(__name__)


class ErasureRegistryError(Exception):
    """Raised for registration conflicts (two contributors, one scope)."""


class SubjectErasureRegistry:
    """Contributors collected from the active modules, keyed by scope.

    Mirrors :class:`~app.core.agents.tools.registry.ToolRegistry`: the
    loader calls :meth:`register_from` for every mounted module, and
    ``gdpr`` pulls :meth:`contributors` inside the erasure transaction.
    A scope with no registered contributor produces no coverage row.

    Boot-only writes: the only production writer is mount (plus tests via
    :meth:`clear`); nothing mutates the registry during a request, so no
    lock is needed. Like ``ToolRegistry.unregister_module``, the uninstall
    path relies on rebuild-at-boot from the active modules instead of
    hot-unwiring.
    """

    def __init__(self) -> None:
        self._contributors: dict[str, ErasureContributor] = {}
        self._owners: dict[str, str] = {}  # scope -> module_name

    # --- Registration ---------------------------------------------------

    def register_from(self, module: BaseModule) -> None:
        """Collect every erasure contributor a module exposes."""
        for contributor in module.get_erasure_contributors():
            scope = contributor.scope
            if scope in self._contributors:
                raise ErasureRegistryError(
                    f"Erasure scope '{scope}' is already registered (owner: {self._owners[scope]})"
                )
            self._contributors[scope] = contributor
            self._owners[scope] = module.name
            logger.info("Registered erasure contributor: %s", scope)

    def unregister_module(self, module_name: str) -> None:
        """Drop every contributor owned by ``module_name``."""
        to_drop = [s for s, owner in self._owners.items() if owner == module_name]
        for scope in to_drop:
            del self._contributors[scope]
            del self._owners[scope]

    def clear(self) -> None:
        """Reset the registry. Test-only."""
        self._contributors.clear()
        self._owners.clear()

    # --- Introspection ---------------------------------------------------

    def get(self, scope: str) -> ErasureContributor | None:
        return self._contributors.get(scope)

    def scopes(self) -> list[str]:
        """All registered scopes, sorted for deterministic coverage order."""
        return sorted(self._contributors)

    def contributors(self) -> list[ErasureContributor]:
        """Registered contributors in deterministic (scope-sorted) order."""
        return [self._contributors[s] for s in self.scopes()]


erasure_registry = SubjectErasureRegistry()
