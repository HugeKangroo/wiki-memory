from __future__ import annotations

from pathlib import Path

from memory_substrate.application.graph.health import GraphHealthReporter
from memory_substrate.application.graph.sync import GraphSyncService
from memory_substrate.application.maintain.lifecycle import MaintenanceLifecycle
from memory_substrate.domain.services.repair_engine import RepairEngine
from memory_substrate.domain.services.structure_validator import StructureValidator
from memory_substrate.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from memory_substrate.projections.markdown.projector import MarkdownProjector


class MaintainService:
    def __init__(self, root: str | Path, graph_backend=None) -> None:
        """Create a maintain service bound to one memory-substrate root.

        Args:
            root: Memory-substrate root directory to validate, repair, reindex, or consolidate.

        Returns:
            None.
        """
        self.root = Path(root)
        self.structure_runner = StructureValidator(self.root)
        self.repair_engine = RepairEngine(self.root)
        self.audit_repository = FsAuditRepository(self.root)
        self.projector = MarkdownProjector(self.root)
        self.lifecycle = MaintenanceLifecycle(self.root)
        self.graph_sync = GraphSyncService(self.root, graph_backend) if graph_backend is not None else None
        self.graph_health = GraphHealthReporter(self.root, graph_backend) if graph_backend is not None else None

    def structure(self) -> dict:
        """Validate memory object structure and projection consistency.

        Returns:
            Maintain report with structural issues and projection warnings.
        """
        report = self.structure_runner.run()
        return {
            "result_type": "structure_report",
            "data": report,
            "warnings": [],
        }

    def audit(self, max_items: int = 100) -> dict:
        """Return recent audit events from the memory store.

        Args:
            max_items: Maximum number of audit events to return from the tail of the log.

        Returns:
            Audit log result containing recent events.
        """
        events = self.audit_repository.list()[-max_items:]
        return {
            "result_type": "audit_log",
            "data": {"events": events},
            "warnings": [],
        }

    def reindex(self) -> dict:
        """Rebuild generated projections from the canonical object store.

        Returns:
            Reindex result with projection write metadata.
        """
        result = self.projector.rebuild()
        if self.graph_sync is not None:
            result = {**result, "graph_sync": self.graph_sync.sync_all()}
        return {
            "result_type": "reindex_result",
            "data": result,
            "warnings": [],
        }

    def repair(self) -> dict:
        """Apply safe automatic repairs for known structural issues.

        Returns:
            Repair result with patch, audit, and changed object metadata.
        """
        result = self.repair_engine.repair_safe_missing_references()
        return {
            "result_type": "repair_result",
            "data": result,
            "warnings": [],
        }

    def promote_candidates(self, min_confidence: float = 0.75, min_evidence: int = 1) -> dict:
        """Promote eligible candidate knowledge items to active status.

        Args:
            min_confidence: Minimum confidence required before promotion.
            min_evidence: Minimum number of evidence references required before promotion.

        Returns:
            Maintenance mutation result with patch metadata and promoted item count.
        """
        return self.lifecycle.promote_candidates(min_confidence=min_confidence, min_evidence=min_evidence)

    def merge_duplicates(self) -> dict:
        """Merge duplicate fact knowledge items and supersede losing records.

        Returns:
            Maintenance mutation result with patch metadata and merged item count.
        """
        return self.lifecycle.merge_duplicates()

    def decay_stale(self, reference_time: str | None = None, stale_after_days: int = 30) -> dict:
        """Mark old active or candidate knowledge as stale.

        Args:
            reference_time: Optional ISO timestamp used as the freshness reference.
            stale_after_days: Age threshold in days after last verification.

        Returns:
            Maintenance mutation result with patch metadata and decayed item count.
        """
        return self.lifecycle.decay_stale(reference_time=reference_time, stale_after_days=stale_after_days)

    def report(
        self,
        min_confidence: float = 0.75,
        min_evidence: int = 1,
        reference_time: str | None = None,
        stale_after_days: int = 30,
    ) -> dict:
        """Summarize maintenance opportunities without mutating memory.

        Args:
            min_confidence: Minimum confidence used to identify promotable candidates.
            min_evidence: Minimum evidence count used to identify promotable candidates.
            reference_time: Optional ISO timestamp used as the stale reference.
            stale_after_days: Age threshold in days after last verification.

        Returns:
            Maintenance report containing promotable, low-evidence, stale, and duplicate knowledge identifiers.
        """
        report = self.lifecycle.report(
            min_confidence=min_confidence,
            min_evidence=min_evidence,
            reference_time=reference_time,
            stale_after_days=stale_after_days,
        )
        if self.graph_health is not None:
            report["data"]["graph"] = self.graph_health.report()
        return report

    def cycle(
        self,
        min_confidence: float = 0.75,
        min_evidence: int = 1,
        reference_time: str | None = None,
        stale_after_days: int = 30,
    ) -> dict:
        """Run the full memory maintenance cycle.

        Args:
            min_confidence: Minimum confidence required for candidate promotion.
            min_evidence: Minimum evidence count required for candidate promotion.
            reference_time: Optional ISO timestamp used as the stale reference.
            stale_after_days: Age threshold in days after last verification.

        Returns:
            Combined maintenance result with promoted, merged, decayed, patch, audit, and projection metadata.
        """
        return self.lifecycle.cycle(
            min_confidence=min_confidence,
            min_evidence=min_evidence,
            reference_time=reference_time,
            stale_after_days=stale_after_days,
        )
