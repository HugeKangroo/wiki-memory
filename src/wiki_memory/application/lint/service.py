from __future__ import annotations

from pathlib import Path

from wiki_memory.domain.services.repair_engine import RepairEngine
from wiki_memory.domain.services.structure_lint import StructureLintRunner
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


class LintService:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.structure_runner = StructureLintRunner(self.root)
        self.repair_engine = RepairEngine(self.root)
        self.audit_repository = FsAuditRepository(self.root)
        self.projector = MarkdownProjector(self.root)

    def structure(self) -> dict:
        report = self.structure_runner.run()
        return {
            "result_type": "lint_report",
            "data": report,
            "warnings": [],
        }

    def audit(self, max_items: int = 100) -> dict:
        events = self.audit_repository.list()[-max_items:]
        return {
            "result_type": "audit_log",
            "data": {"events": events},
            "warnings": [],
        }

    def reindex(self) -> dict:
        result = self.projector.rebuild()
        return {
            "result_type": "reindex_result",
            "data": result,
            "warnings": [],
        }

    def repair(self) -> dict:
        result = self.repair_engine.repair_safe_missing_references()
        return {
            "result_type": "repair_result",
            "data": result,
            "warnings": [],
        }
