from __future__ import annotations

from typing import Any, Protocol


class GraphBackend(Protocol):
    """Project-owned graph backend contract for memory-core integrations."""

    def upsert_episode(self, episode: dict[str, Any]) -> dict[str, Any]:
        """Create or replace one source episode record."""

    def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Create or replace one graph entity record."""

    def upsert_relation(self, relation: dict[str, Any]) -> dict[str, Any]:
        """Create or replace one typed graph relation record."""

    def upsert_knowledge(self, knowledge: dict[str, Any]) -> dict[str, Any]:
        """Create or replace one durable knowledge record."""

    def link_evidence(self, object_type: str, object_id: str, evidence_refs: list[dict[str, Any]]) -> dict[str, Any]:
        """Attach evidence references to an existing graph record."""

    def search(self, query: str, scope_refs: list[str] | None = None, max_items: int = 10) -> list[dict[str, Any]]:
        """Return ranked graph records matching the query."""

    def neighborhood(self, object_id: str, depth: int = 1, max_items: int = 20) -> dict[str, Any]:
        """Return nearby nodes and relations around one graph object."""

    def temporal_lookup(self, reference_time: str, scope_refs: list[str] | None = None) -> dict[str, Any]:
        """Return records valid at the supplied ISO timestamp."""

    def health(self) -> dict[str, Any]:
        """Return backend health and record counts."""

    def rebuild(self) -> dict[str, Any]:
        """Rebuild derived graph state when the backend supports it."""

    def export_scope(self, scope_ref: str) -> dict[str, Any]:
        """Export records that belong to one memory scope."""
