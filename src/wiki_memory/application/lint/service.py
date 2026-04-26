from __future__ import annotations

from pathlib import Path

from wiki_memory.domain.services.repair_engine import RepairEngine
from wiki_memory.domain.services.structure_lint import StructureLintRunner
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


class LintService:
    def __init__(self, root: str | Path) -> None:
        """Create a lint service bound to one wiki-memory root.

        Args:
            root: Wiki-memory root directory to validate, repair, or reindex.

        Returns:
            None.
        """
        self.root = Path(root)
        self.structure_runner = StructureLintRunner(self.root)
        self.repair_engine = RepairEngine(self.root)
        self.audit_repository = FsAuditRepository(self.root)
        self.projector = MarkdownProjector(self.root)

    def structure(self) -> dict:
        """Validate wiki-memory object structure and projection consistency.

        Returns:
            Lint report with structural issues and projection warnings.
        """
        report = self.structure_runner.run()
        return {
            "result_type": "lint_report",
            "data": report,
            "warnings": [],
        }

    def audit(self, max_items: int = 100) -> dict:
        """Return recent audit events from the wiki store.

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
