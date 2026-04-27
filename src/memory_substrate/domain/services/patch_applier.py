from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from memory_substrate.domain.protocols.audit_event import AuditEvent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_audit_id() -> str:
    return f"aud:{uuid4().hex}"


@dataclass(slots=True)
class PatchApplyResult:
    patch_id: str
    applied_operations: int = 0
    affected_object_ids: list[str] = field(default_factory=list)
    audit_event_ids: list[str] = field(default_factory=list)


class PatchApplyError(RuntimeError):
    """Raised when a patch operation cannot be applied safely."""


class PatchApplier:
    """Applies patch operations to the object store and appends audit events."""

    def __init__(self, object_repository, patch_repository, audit_repository) -> None:
        self.object_repository = object_repository
        self.patch_repository = patch_repository
        self.audit_repository = audit_repository

    def apply(self, patch) -> PatchApplyResult:
        result = PatchApplyResult(patch_id=patch.id)
        staged_objects = self._build_staged_objects(patch)

        self.patch_repository.save(patch)

        for operation in patch.operations:
            before = self.object_repository.get(operation.object_type, operation.object_id)
            after = staged_objects.get((operation.object_type, operation.object_id))
            self._commit_operation(operation, after)
            event = AuditEvent(
                id=new_audit_id(),
                event_type=operation.op,
                actor=patch.source,
                target={
                    "object_type": operation.object_type,
                    "object_id": operation.object_id,
                },
                before=before or {},
                after=after or {},
                reason=operation.changes.get("reason", ""),
                timestamp=utc_now_iso(),
            )
            self.audit_repository.append(event)
            result.applied_operations += 1
            result.affected_object_ids.append(operation.object_id)
            result.audit_event_ids.append(event.id)

        return result

    def _build_staged_objects(self, patch) -> dict[tuple[str, str], dict | None]:
        current_state: dict[tuple[str, str], dict | None] = {}
        staged_state: dict[tuple[str, str], dict | None] = {}

        for operation in patch.operations:
            key = (operation.object_type, operation.object_id)
            if key not in current_state:
                current_state[key] = self.object_repository.get(*key)
            before = staged_state.get(key, current_state[key])
            after = self._resolve_operation(operation, before)
            staged_state[key] = after

        return staged_state

    def _resolve_operation(self, operation, before: dict | None) -> dict | None:
        if operation.op == "create_object":
            if before is not None:
                raise PatchApplyError(
                    f'Cannot create existing object: {operation.object_type}:{operation.object_id}'
                )
            payload = {
                "id": operation.object_id,
                **operation.changes,
            }
            payload.setdefault("created_at", utc_now_iso())
            payload.setdefault("updated_at", payload["created_at"])
            return payload

        if operation.op == "update_object":
            if before is None:
                raise PatchApplyError(
                    f'Cannot update missing object: {operation.object_type}:{operation.object_id}'
                )
            payload = {**before, **operation.changes, "updated_at": utc_now_iso()}
            return payload

        if operation.op == "change_status":
            if before is None:
                raise PatchApplyError(
                    f'Cannot change status of missing object: {operation.object_type}:{operation.object_id}'
                )
            status = operation.changes["status"]
            payload = {**before, "status": status, "updated_at": utc_now_iso()}
            return payload

        if operation.op == "archive_object":
            if before is None:
                raise PatchApplyError(
                    f'Cannot archive missing object: {operation.object_type}:{operation.object_id}'
                )
            payload = {**before, "status": "archived", "updated_at": utc_now_iso()}
            if "lifecycle_state" in payload:
                payload["lifecycle_state"] = "archived"
            return payload

        if operation.op == "delete_object":
            if before is None:
                raise PatchApplyError(
                    f'Cannot delete missing object: {operation.object_type}:{operation.object_id}'
                )
            return None

        raise PatchApplyError(f"Unsupported patch operation: {operation.op}")

    def _commit_operation(self, operation, after: dict | None) -> None:
        if operation.op == "delete_object":
            self.object_repository.delete(operation.object_type, operation.object_id)
            return
        if after is None:
            raise PatchApplyError(
                f'Patch operation resolved to empty payload unexpectedly: {operation.op}'
            )
        self.object_repository.save(operation.object_type, after)
