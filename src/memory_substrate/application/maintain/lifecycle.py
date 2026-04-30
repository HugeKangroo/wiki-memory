from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory_substrate.domain.protocols.memory_patch import PatchOperation, MemoryPatch
from memory_substrate.domain.services.concept_candidates import ConceptCandidateDiscovery
from memory_substrate.domain.services.ids import new_id
from memory_substrate.domain.services.patch_applier import PatchApplier, utc_now_iso
from memory_substrate.domain.services.soft_duplicates import KnowledgeSoftDuplicateDetector
from memory_substrate.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from memory_substrate.projections.markdown.projector import MarkdownProjector


class MaintenanceLifecycle:
    def __init__(self, root: str | Path) -> None:
        """Create a memory maintenance service bound to one memory-substrate root.

        Args:
            root: Memory-substrate root directory to inspect and mutate.

        Returns:
            None.
        """
        self.root = Path(root)
        self.object_repository = FsObjectRepository(self.root)
        self.patch_repository = FsPatchRepository(self.root)
        self.audit_repository = FsAuditRepository(self.root)
        self.patch_applier = PatchApplier(
            object_repository=self.object_repository,
            patch_repository=self.patch_repository,
            audit_repository=self.audit_repository,
        )
        self.projector = MarkdownProjector(self.root)
        self.soft_duplicates = KnowledgeSoftDuplicateDetector()
        self.concept_candidates = ConceptCandidateDiscovery()

    def promote_candidates(self, min_confidence: float = 0.75, min_evidence: int = 1) -> dict:
        """Promote eligible candidate knowledge items to active status.

        Args:
            min_confidence: Minimum confidence required before promotion.
            min_evidence: Minimum number of evidence references required before promotion.

        Returns:
            Maintenance mutation result with patch metadata and promoted item count.
        """
        operations: list[PatchOperation] = []
        for item in self.object_repository.list("knowledge"):
            if item.get("status") != "candidate":
                continue
            if float(item.get("confidence", 0.0)) < min_confidence:
                continue
            if len(item.get("evidence_refs", [])) < min_evidence:
                continue
            if not item.get("subject_refs"):
                continue
            operations.append(
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=item["id"],
                    changes={
                        "status": "active",
                        "last_verified_at": utc_now_iso(),
                        "reason": "maintain_promote_candidates",
                    },
                )
            )
        result = self._apply_operations(operations)
        return {
            **result,
            "promoted": len(operations),
        }

    def merge_duplicates(self) -> dict:
        """Merge duplicate fact knowledge items and supersede losing records.

        Returns:
            Maintenance mutation result with patch metadata and merged item count.
        """
        operations: list[PatchOperation] = []
        merged = 0
        for duplicates in self._duplicate_groups():
            if len(duplicates) < 2:
                continue
            winner = self._pick_winner(duplicates)
            loser_ids = [item["id"] for item in duplicates if item["id"] != winner["id"]]
            merged_evidence = self._merge_evidence_refs(duplicates)
            operations.append(
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=winner["id"],
                    changes={
                        "evidence_refs": merged_evidence,
                        "confidence": max(float(item.get("confidence", 0.0)) for item in duplicates),
                        "status": self._strongest_status(duplicates),
                        "reason": f"maintain_merge_winner:{','.join(loser_ids)}",
                    },
                )
            )
            for loser in duplicates:
                if loser["id"] == winner["id"]:
                    continue
                operations.append(
                    PatchOperation(
                        op="update_object",
                        object_type="knowledge",
                        object_id=loser["id"],
                        changes={
                            "status": "superseded",
                            "valid_until": utc_now_iso(),
                            "reason": f"maintain_merge_loser:{winner['id']}",
                        },
                    )
                )
            merged += len(duplicates) - 1
        result = self._apply_operations(operations)
        return {
            **result,
            "merged": merged,
        }

    def resolve_duplicates(
        self,
        *,
        outcome: str,
        knowledge_ids: list[str],
        reason: str,
        canonical_knowledge_id: str | None = None,
        updates: list[dict] | None = None,
    ) -> dict:
        """Apply an explicit review outcome for an advisory soft duplicate candidate."""
        outcome = str(outcome)
        reason = str(reason or "").strip()
        if not reason:
            raise ValueError("resolve_duplicates requires a non-empty reason")
        ids = self._validated_resolution_ids(knowledge_ids)
        self._ensure_soft_duplicate_candidate(ids)
        timestamp = utc_now_iso()
        operations: list[PatchOperation] = []

        if outcome == "supersede":
            if canonical_knowledge_id not in ids:
                raise ValueError("canonical_knowledge_id must be one of knowledge_ids")
            for knowledge_id in ids:
                if knowledge_id == canonical_knowledge_id:
                    existing = self.object_repository.get("knowledge", knowledge_id) or {}
                    operations.append(
                        PatchOperation(
                            op="update_object",
                            object_type="knowledge",
                            object_id=knowledge_id,
                            changes={
                                "status": "active",
                                "valid_from": existing.get("valid_from") or timestamp,
                                "last_verified_at": timestamp,
                                "reason": f"maintain_resolve_duplicates:supersede:{reason}",
                            },
                        )
                    )
                    continue
                operations.append(
                    PatchOperation(
                        op="update_object",
                        object_type="knowledge",
                        object_id=knowledge_id,
                        changes={
                            "status": "superseded",
                            "valid_until": timestamp,
                            "reason": f"maintain_resolve_duplicates:superseded_by:{canonical_knowledge_id}:{reason}",
                        },
                    )
                )
        elif outcome == "keep_both":
            operations.extend(self._keep_both_resolution_operations(ids, updates or [], reason, timestamp))
        elif outcome == "contest":
            for knowledge_id in ids:
                operations.append(
                    PatchOperation(
                        op="update_object",
                        object_type="knowledge",
                        object_id=knowledge_id,
                        changes={
                            "status": "contested",
                            "reason": f"maintain_resolve_duplicates:contest:{reason}",
                            "last_verified_at": timestamp,
                        },
                    )
                )
        else:
            raise ValueError(f"Unsupported duplicate resolution outcome: {outcome}")

        result = self._apply_operations(operations)
        return {
            **result,
            "outcome": outcome,
            "resolved": len(ids),
            "knowledge_ids": ids,
        }

    def decay_stale(self, reference_time: str | None = None, stale_after_days: int = 30) -> dict:
        """Mark old active or candidate knowledge as stale.

        Args:
            reference_time: Optional ISO timestamp used as the freshness reference.
            stale_after_days: Age threshold in days after last verification.

        Returns:
            Maintenance mutation result with patch metadata and decayed item count.
        """
        now = self._parse_time(reference_time) if reference_time else self._parse_time(utc_now_iso())
        threshold = now - timedelta(days=stale_after_days)
        operations: list[PatchOperation] = []
        for item in self.object_repository.list("knowledge"):
            if item.get("status") not in {"active", "candidate"}:
                continue
            verified_at = item.get("last_verified_at")
            if not verified_at:
                continue
            if self._parse_time(verified_at) >= threshold:
                continue
            operations.append(
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=item["id"],
                    changes={
                        "status": "stale",
                        "reason": "maintain_decay_stale",
                    },
                )
            )
        result = self._apply_operations(operations)
        return {
            **result,
            "decayed": len(operations),
        }

    def archive_source(self, source_id: str, reason: str) -> dict:
        """Archive one source and stale knowledge whose evidence depends only on it.

        Args:
            source_id: Source object id to archive.
            reason: Durable audit reason explaining why the source is retired.

        Returns:
            Maintenance mutation result with affected knowledge diagnostics.
        """
        source_id = str(source_id or "").strip()
        reason = str(reason or "").strip()
        if not source_id:
            raise ValueError("archive_source requires source_id")
        if not reason:
            raise ValueError("archive_source requires a non-empty reason")
        if self.object_repository.get("source", source_id) is None:
            raise ValueError(f"Source not found: {source_id}")

        stale_knowledge_ids: list[str] = []
        partially_affected_knowledge_ids: list[str] = []
        operations = [
            PatchOperation(
                op="update_object",
                object_type="source",
                object_id=source_id,
                changes={
                    "status": "archived",
                    "reason": f"maintain_archive_source:{source_id}:{reason}",
                },
            )
        ]

        for item in self.object_repository.list("knowledge"):
            if item.get("status") in {"superseded", "archived"}:
                continue
            evidence_source_ids = self._evidence_source_ids(item)
            if source_id not in evidence_source_ids:
                continue
            if evidence_source_ids <= {source_id}:
                stale_knowledge_ids.append(item["id"])
                operations.append(
                    PatchOperation(
                        op="update_object",
                        object_type="knowledge",
                        object_id=item["id"],
                        changes={
                            "status": "stale",
                            "reason": f"maintain_archive_source:{source_id}:{reason}",
                        },
                    )
                )
            else:
                partially_affected_knowledge_ids.append(item["id"])

        result = self._apply_operations(operations)
        return {
            **result,
            "archived_source_id": source_id,
            "stale_knowledge_ids": sorted(stale_knowledge_ids),
            "partially_affected_knowledge_ids": sorted(partially_affected_knowledge_ids),
        }

    def report(
        self,
        min_confidence: float = 0.75,
        min_evidence: int = 1,
        reference_time: str | None = None,
        stale_after_days: int = 30,
    ) -> dict:
        """Summarize memory maintenance opportunities without mutating memory.

        Args:
            min_confidence: Minimum confidence used to identify promotable candidates.
            min_evidence: Minimum evidence count used to identify promotable candidates.
            reference_time: Optional ISO timestamp used as the stale reference.
            stale_after_days: Age threshold in days after last verification.

        Returns:
            Report containing promotable, low-evidence, stale, and duplicate knowledge identifiers.
        """
        now = self._parse_time(reference_time) if reference_time else self._parse_time(utc_now_iso())
        threshold = now - timedelta(days=stale_after_days)
        promote_candidate_ids: list[str] = []
        low_evidence_candidate_ids: list[str] = []
        stale_candidate_ids: list[str] = []
        governance_violations: list[dict] = []
        fact_check_issues = self._fact_check_issues(reference_time=now)

        for item in self.object_repository.list("knowledge"):
            status = item.get("status")
            evidence_count = len(item.get("evidence_refs", []))
            confidence = float(item.get("confidence", 0.0))
            governance_violations.extend(self._governance_violations(item, evidence_count))
            if status == "candidate" and confidence >= min_confidence and item.get("subject_refs"):
                if evidence_count >= min_evidence:
                    promote_candidate_ids.append(item["id"])
                else:
                    low_evidence_candidate_ids.append(item["id"])
            if status in {"active", "candidate"} and item.get("last_verified_at"):
                if self._parse_time(item["last_verified_at"]) < threshold:
                    stale_candidate_ids.append(item["id"])

        duplicate_groups = [
            [item["id"] for item in sorted(group, key=lambda candidate: str(candidate.get("title") or candidate["id"]))]
            for group in self._duplicate_groups()
            if len(group) > 1
        ]
        duplicate_groups.sort(key=lambda group: group[0])
        knowledge_items = self.object_repository.list("knowledge")
        soft_duplicate_candidates = self.soft_duplicates.groups(knowledge_items)
        candidate_analysis = self.concept_candidates.analyze(
            sources=self.object_repository.list("source"),
            knowledge_items=knowledge_items,
            nodes=self.object_repository.list("node"),
        )
        concept_candidates = candidate_analysis["candidates"]

        return {
            "result_type": "maintain_report",
            "data": {
                "promote_candidate_ids": sorted(promote_candidate_ids),
                "low_evidence_candidate_ids": sorted(low_evidence_candidate_ids),
                "stale_candidate_ids": sorted(stale_candidate_ids),
                "duplicate_groups": duplicate_groups,
                "soft_duplicate_candidates": soft_duplicate_candidates,
                "concept_candidates": concept_candidates,
                "candidate_diagnostics": candidate_analysis["candidate_diagnostics"],
                "fact_check_issues": fact_check_issues,
                "governance_violations": sorted(governance_violations, key=lambda item: item["object_id"]),
                "counts": {
                    "promote_candidates": len(promote_candidate_ids),
                    "low_evidence_candidates": len(low_evidence_candidate_ids),
                    "stale_candidates": len(stale_candidate_ids),
                    "duplicate_groups": len(duplicate_groups),
                    "soft_duplicate_candidates": len(soft_duplicate_candidates),
                    "concept_candidates": len(concept_candidates),
                    "fact_check_issues": len(fact_check_issues),
                    "governance_violations": len(governance_violations),
                },
            },
            "warnings": [],
        }

    def _governance_violations(self, item: dict, evidence_count: int) -> list[dict]:
        if item.get("status") != "active" or evidence_count > 0:
            return []
        memory_source = self._memory_source(item)
        if memory_source in {"user_declared", "human_curated"}:
            return []
        return [
            {
                "object_id": item["id"],
                "kind": "active_knowledge_without_evidence",
                "severity": "warning",
                "summary": "Active knowledge has no evidence and is not user-declared or human-curated.",
                "memory_source": memory_source or "unknown",
            }
        ]

    def _memory_source(self, item: dict) -> str | None:
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            return None
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            return None
        value = metadata.get("memory_source")
        return str(value) if value else None

    def _fact_check_issues(self, reference_time: datetime) -> list[dict]:
        issues = [
            *self._similar_entity_name_issues(),
            *self._stale_fact_issues(reference_time),
            *self._relationship_mismatch_issues(reference_time),
        ]
        return sorted(issues, key=lambda item: (item["kind"], item.get("object_id", ""), ",".join(item.get("object_ids", []))))

    def _similar_entity_name_issues(self) -> list[dict]:
        nodes = self.object_repository.list("node")
        buckets: dict[str, list[dict]] = {}
        for node in nodes:
            names = [str(node.get("name") or node.get("title") or node["id"])]
            names.extend(str(alias) for alias in node.get("aliases", []) if alias)
            for name in names:
                normalized = self._entity_name_key(name)
                if normalized:
                    buckets.setdefault(normalized, []).append(node)
        issues = []
        for candidates in buckets.values():
            unique = {candidate["id"]: candidate for candidate in candidates}
            if len(unique) < 2:
                continue
            ids = sorted(unique)
            issues.append(
                {
                    "kind": "similar_entity_name",
                    "severity": "warning",
                    "object_ids": ids,
                    "summary": "Multiple nodes have names or aliases that normalize to the same key.",
                    "next_actions": ["clarify_scope", "merge_if_same_entity", "keep_both_if_distinct"],
                }
            )
        return issues

    def _entity_name_key(self, name: str) -> str:
        return "".join(character.lower() for character in name if character.isalnum())

    def _stale_fact_issues(self, reference_time: datetime) -> list[dict]:
        issues = []
        for item in self.object_repository.list("knowledge"):
            if item.get("kind") != "fact" or item.get("status") != "active":
                continue
            valid_until = item.get("valid_until")
            if not valid_until:
                continue
            if self._parse_time(valid_until) >= reference_time:
                continue
            issues.append(
                {
                    "kind": "stale_fact",
                    "severity": "warning",
                    "object_id": item["id"],
                    "summary": "Active fact is past its validity window.",
                    "valid_until": valid_until,
                    "next_actions": ["verify", "supersede", "contest"],
                }
            )
        return issues

    def _relationship_mismatch_issues(self, reference_time: datetime) -> list[dict]:
        buckets: dict[tuple[str, str], list[dict]] = {}
        for item in self.object_repository.list("knowledge"):
            if item.get("kind") != "fact" or item.get("status") in {"superseded", "archived", "contested"}:
                continue
            valid_until = item.get("valid_until")
            if valid_until and self._parse_time(valid_until) < reference_time:
                continue
            payload = item.get("payload", {})
            if not isinstance(payload, dict):
                continue
            predicate = payload.get("predicate")
            if not predicate:
                continue
            subject = self._fact_subject(item, payload)
            if not subject:
                continue
            buckets.setdefault((subject, str(predicate)), []).append(item)
        issues = []
        for (subject, predicate), items in buckets.items():
            values: dict[str, list[dict]] = {}
            for item in items:
                payload = item.get("payload", {})
                value_key = self._normalize_value(
                    {
                        "value": payload.get("value"),
                        "object": payload.get("object"),
                    }
                )
                values.setdefault(value_key, []).append(item)
            if len(values) < 2:
                continue
            ids = sorted(item["id"] for group in values.values() for item in group)
            issues.append(
                {
                    "kind": "relationship_mismatch",
                    "severity": "warning",
                    "object_ids": ids,
                    "subject": subject,
                    "predicate": predicate,
                    "summary": "Structured facts assert different values for the same subject and predicate.",
                    "next_actions": ["review_evidence", "contest", "supersede", "keep_both_with_scopes"],
                }
            )
        return issues

    def _fact_subject(self, item: dict, payload: dict) -> str:
        subject_refs = item.get("subject_refs", [])
        if subject_refs:
            return str(subject_refs[0])
        subject = payload.get("subject")
        return str(subject) if subject else ""

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
        promoted = self.promote_candidates(min_confidence=min_confidence, min_evidence=min_evidence)
        merged = self.merge_duplicates()
        decayed = self.decay_stale(reference_time=reference_time, stale_after_days=stale_after_days)
        audit_event_ids = [
            *promoted.get("audit_event_ids", []),
            *merged.get("audit_event_ids", []),
            *decayed.get("audit_event_ids", []),
        ]
        patch_ids = [patch_id for patch_id in (promoted["patch_id"], merged["patch_id"], decayed["patch_id"]) if patch_id]
        projection = self.projector.rebuild()
        return {
            "status": "completed",
            "promoted": promoted["promoted"],
            "merged": merged["merged"],
            "decayed": decayed["decayed"],
            "patch_ids": patch_ids,
            "audit_event_ids": audit_event_ids,
            "projection_count": projection["count"],
        }

    def _apply_operations(self, operations: list[PatchOperation]) -> dict:
        if not operations:
            projection = self.projector.rebuild()
            return {
                "status": "noop",
                "patch_id": None,
                "audit_event_ids": [],
                "projection_count": projection["count"],
            }
        patch = MemoryPatch(
            id=new_id("patch"),
            source={"type": "system", "id": "memory.maintain"},
            operations=operations,
            created_at=utc_now_iso(),
        )
        result = self.patch_applier.apply(patch)
        projection = self.projector.rebuild()
        return {
            "status": "completed",
            "patch_id": result.patch_id,
            "audit_event_ids": result.audit_event_ids,
            "projection_count": projection["count"],
        }

    def _normalize_value(self, value) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def _duplicate_groups(self) -> list[list[dict]]:
        buckets: dict[tuple[str, str, str], list[dict]] = {}
        for item in self.object_repository.list("knowledge"):
            if item.get("status") in {"superseded", "archived"}:
                continue
            if item.get("kind") != "fact":
                continue
            subject_refs = item.get("subject_refs", [])
            payload = item.get("payload", {})
            if not subject_refs or not isinstance(payload, dict) or "predicate" not in payload:
                continue
            key = (
                str(subject_refs[0]),
                str(payload.get("predicate")),
                self._normalize_value(payload.get("value")),
                self._normalize_value(payload.get("object")),
            )
            buckets.setdefault(key, []).append(item)
        return list(buckets.values())

    def _merge_evidence_refs(self, items: list[dict]) -> list[dict]:
        seen: set[tuple[str, str]] = set()
        merged: list[dict] = []
        for item in items:
            for evidence in item.get("evidence_refs", []):
                source_id = str(evidence.get("source_id"))
                segment_id = str(evidence.get("segment_id"))
                key = (source_id, segment_id)
                if key in seen:
                    continue
                seen.add(key)
                merged.append({"source_id": source_id, "segment_id": segment_id})
        return merged

    def _evidence_source_ids(self, item: dict) -> set[str]:
        source_ids: set[str] = set()
        for evidence in item.get("evidence_refs", []):
            if isinstance(evidence, dict) and evidence.get("source_id"):
                source_ids.add(str(evidence["source_id"]))
        return source_ids

    def _pick_winner(self, duplicates: list[dict]) -> dict:
        def sort_key(item: dict) -> tuple[int, float, datetime, float]:
            status_rank = {
                "active": 3,
                "candidate": 2,
                "stale": 1,
                "contested": 0,
                "superseded": -1,
                "archived": -2,
            }
            confidence = float(item.get("confidence", 0.0))
            verified_at = self._parse_time(item.get("last_verified_at"))
            created_at = self._parse_time(item.get("created_at"))
            return (
                status_rank.get(str(item.get("status", "")), 0),
                confidence,
                verified_at,
                -created_at.timestamp(),
            )

        return max(duplicates, key=sort_key)

    def _strongest_status(self, duplicates: list[dict]) -> str:
        status_rank = {
            "active": 3,
            "candidate": 2,
            "stale": 1,
            "contested": 0,
            "superseded": -1,
            "archived": -2,
        }
        return max(
            (str(item.get("status", "candidate")) for item in duplicates),
            key=lambda status: status_rank.get(status, 0),
        )

    def _validated_resolution_ids(self, knowledge_ids: list[str]) -> list[str]:
        ids = [str(knowledge_id) for knowledge_id in knowledge_ids if str(knowledge_id)]
        if len(set(ids)) != len(ids):
            raise ValueError("knowledge_ids must not contain duplicates")
        if len(ids) < 2:
            raise ValueError("resolve_duplicates requires at least two knowledge_ids")
        for knowledge_id in ids:
            item = self.object_repository.get("knowledge", knowledge_id)
            if item is None:
                raise ValueError(f"Knowledge not found: {knowledge_id}")
            if item.get("status") in {"superseded", "archived"}:
                raise ValueError(f"Knowledge is not resolvable: {knowledge_id}")
        return ids

    def _ensure_soft_duplicate_candidate(self, knowledge_ids: list[str]) -> None:
        requested = set(knowledge_ids)
        candidate_sets = [set(group["object_ids"]) for group in self.soft_duplicates.groups(self.object_repository.list("knowledge"))]
        if requested in candidate_sets:
            return
        covered: set[str] = set()
        for candidate_set in candidate_sets:
            if candidate_set <= requested:
                covered.update(candidate_set)
        if requested <= covered:
            return
        raise ValueError("knowledge_ids are not a current soft duplicate candidate")

    def _keep_both_resolution_operations(
        self,
        knowledge_ids: list[str],
        updates: list[dict],
        reason: str,
        timestamp: str,
    ) -> list[PatchOperation]:
        if not updates:
            raise ValueError("keep_both requires updates that clarify summary or scope_refs")
        allowed_ids = set(knowledge_ids)
        operations: list[PatchOperation] = []
        for update in updates:
            knowledge_id = str(update.get("knowledge_id") or "")
            if knowledge_id not in allowed_ids:
                raise ValueError("keep_both updates must target only knowledge_ids")
            changes: dict[str, object] = {
                "reason": f"maintain_resolve_duplicates:keep_both:{reason}",
                "last_verified_at": timestamp,
            }
            if "summary" in update:
                summary = str(update.get("summary") or "").strip()
                if not summary:
                    raise ValueError("keep_both summary updates must be non-empty")
                changes["summary"] = summary
            if "scope_refs" in update:
                scope_refs = [str(ref) for ref in update.get("scope_refs", []) if str(ref)]
                if not scope_refs:
                    raise ValueError("keep_both scope_refs updates must be non-empty")
                changes["scope_refs"] = scope_refs
            if set(changes) == {"reason", "last_verified_at"}:
                raise ValueError("keep_both updates must include summary or scope_refs")
            operations.append(
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=knowledge_id,
                    changes=changes,
                )
            )
        return operations

    def _parse_time(self, value: str | None) -> datetime:
        if not value:
            return datetime.min.replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
