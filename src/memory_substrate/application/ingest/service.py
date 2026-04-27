from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.request import urlopen

from memory_substrate.adapters.repo.adapter import RepoAdapter
from memory_substrate.domain.objects.activity import Activity
from memory_substrate.domain.objects.node import Node
from memory_substrate.domain.objects.source import Source, SourceSegment
from memory_substrate.domain.protocols.memory_patch import PatchOperation, MemoryPatch
from memory_substrate.domain.services.ids import new_id, slugify, stable_id
from memory_substrate.domain.services.patch_applier import PatchApplier, utc_now_iso
from memory_substrate.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from memory_substrate.projections.markdown.projector import MarkdownProjector


class IngestService:
    def __init__(self, root: str | Path) -> None:
        """Create an ingest service bound to one memory-substrate root.

        Args:
            root: Memory-substrate root directory that stores canonical objects and projections.

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
        self.repo_adapter = RepoAdapter()
        self.projector = MarkdownProjector(self.root)

    def ingest_repo(self, repo_path: str | Path) -> dict:
        """Scan a repository and write its source, node, knowledge, and activity objects.

        Args:
            repo_path: Local repository path to scan.

        Returns:
            Ingest result with patch, source, node, knowledge, activity, audit, and projection metadata.
        """
        output = self.repo_adapter.ingest(repo_path)
        repo_root = str(Path(repo_path).resolve())
        operations = [
            self._upsert_operation(
                object_type="source",
                object_id=output.source.id,
                changes={
                    "kind": output.source.kind,
                    "origin": output.source.origin,
                    "title": output.source.title,
                    "identity_key": output.source.identity_key,
                    "fingerprint": output.source.fingerprint,
                    "content_type": output.source.content_type,
                    "payload": output.source.payload,
                    "segments": output.source.segments,
                    "metadata": output.source.metadata,
                    "status": output.source.status,
                    "created_at": output.source.created_at,
                    "updated_at": output.source.updated_at,
                },
            )
        ]
        operations.extend(self._archive_missing_repo_objects(repo_root, output))

        for node in output.nodes:
            operations.append(
                self._upsert_operation(
                    object_type="node",
                    object_id=node.id,
                    changes={
                        "kind": node.kind,
                        "name": node.name,
                        "slug": node.slug,
                        "identity_key": node.identity_key,
                        "aliases": node.aliases,
                        "summary": node.summary,
                        "status": node.status,
                        "created_at": node.created_at,
                        "updated_at": node.updated_at,
                    },
                )
            )

        for item in output.knowledge_items:
            operations.append(
                self._upsert_operation(
                    object_type="knowledge",
                    object_id=item.id,
                    changes={
                        "kind": item.kind,
                        "title": item.title,
                        "summary": item.summary,
                        "identity_key": item.identity_key,
                        "subject_refs": item.subject_refs,
                        "evidence_refs": item.evidence_refs,
                        "payload": item.payload,
                        "status": item.status,
                        "confidence": item.confidence,
                        "valid_from": item.valid_from,
                        "valid_until": item.valid_until,
                        "last_verified_at": item.last_verified_at,
                        "created_at": item.created_at,
                        "updated_at": item.updated_at,
                    },
                )
            )

        if output.activity is not None:
            operations.append(
                self._upsert_operation(
                    object_type="activity",
                    object_id=output.activity.id,
                    changes={
                        "kind": output.activity.kind,
                        "title": output.activity.title,
                        "summary": output.activity.summary,
                        "identity_key": output.activity.identity_key,
                        "status": output.activity.status,
                        "started_at": output.activity.started_at,
                        "ended_at": output.activity.ended_at,
                        "related_node_refs": output.activity.related_node_refs,
                        "related_work_item_refs": output.activity.related_work_item_refs,
                        "source_refs": output.activity.source_refs,
                        "produced_object_refs": output.activity.produced_object_refs,
                        "artifact_refs": output.activity.artifact_refs,
                        "created_at": output.activity.created_at,
                        "updated_at": output.activity.updated_at,
                    },
                )
            )

        patch = MemoryPatch(
            id=new_id("patch"),
            source={
                "type": "system",
                "id": "memory.ingest.repo",
                "repo_path": str(Path(repo_path).resolve()),
            },
            operations=operations,
            created_at=utc_now_iso(),
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "patch_id": apply_result.patch_id,
            "source_id": output.source.id,
            "node_ids": [node.id for node in output.nodes],
            "knowledge_ids": [item.id for item in output.knowledge_items],
            "activity_id": output.activity.id if output.activity else None,
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
        }

    def ingest_file(self, file_path: str | Path) -> dict:
        """Ingest a plain text file as a document source.

        Args:
            file_path: Local file path to read.

        Returns:
            Ingest result for the created or updated document source and projection.
        """
        return self._ingest_document(file_path, kind="file", content_type="text")

    def ingest_markdown(self, file_path: str | Path) -> dict:
        """Ingest a Markdown file as a structured document source.

        Args:
            file_path: Local Markdown file path to read.

        Returns:
            Ingest result for the created or updated Markdown source and projection.
        """
        return self._ingest_document(file_path, kind="markdown", content_type="markdown")

    def ingest_web(self, url: str) -> dict:
        """Fetch a web page and ingest its readable text as a source.

        Args:
            url: HTTP or HTTPS URL to fetch.

        Returns:
            Ingest result for the created or updated web source and projection.
        """
        with urlopen(url, timeout=20) as response:
            raw = response.read()
            content_type_header = response.headers.get("content-type", "")
        text = raw.decode("utf-8", errors="replace")
        text = self._html_to_text(text) if "html" in content_type_header or "<html" in text.lower() else text
        return self._ingest_text_source(
            identity=f"source|web|{url}",
            kind="web",
            title=url,
            origin={"url": url},
            text=text,
            content_type="text",
            activity_kind="reading",
            artifact_ref=url,
        )

    def ingest_pdf(self, file_path: str | Path) -> dict:
        """Ingest a PDF path as text when possible or as a binary stub otherwise.

        Args:
            file_path: Local PDF file path to read.

        Returns:
            Ingest result for the created or updated PDF source and projection.
        """
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"PDF path is not a file: {path}")
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="ignore").strip()
        if text and not text.startswith("%PDF"):
            return self._ingest_text_source(
                identity=f"source|pdf|{path}",
                kind="pdf",
                title=path.name,
                origin={"path": str(path)},
                text=text,
                content_type="text",
                activity_kind="reading",
                artifact_ref=str(path),
            )
        return self._ingest_binary_stub(path, kind="pdf", raw=raw)

    def ingest_conversation(self, title: str, messages: list[dict], origin: dict | None = None) -> dict:
        """Ingest chat or meeting messages as a conversation source.

        Args:
            title: Human-readable conversation title.
            messages: Message dictionaries containing role and content fields.
            origin: Optional metadata describing where the conversation came from.

        Returns:
            Ingest result for the created or updated conversation source and projection.
        """
        lines = []
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            lines.append(f"{role}: {content}")
        text = "\n\n".join(lines)
        return self._ingest_text_source(
            identity=f"source|conversation|{title}|{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
            kind="conversation",
            title=title,
            origin=origin or {"title": title},
            text=text,
            content_type="structured",
            activity_kind="meeting",
            artifact_ref=title,
        )

    def _upsert_operation(self, object_type: str, object_id: str, changes: dict) -> PatchOperation:
        exists = self.object_repository.exists(object_type, object_id)
        payload = dict(changes)
        if exists:
            payload.pop("created_at", None)
        return PatchOperation(
            op="update_object" if exists else "create_object",
            object_type=object_type,
            object_id=object_id,
            changes=payload,
        )

    def _archive_missing_repo_objects(self, repo_root: str, output) -> list[PatchOperation]:
        operations: list[PatchOperation] = []
        expected_ids = {
            "node": {node.id for node in output.nodes},
            "knowledge": {item.id for item in output.knowledge_items},
        }
        identity_prefixes = {
            "node": (
                f"node|repo|{repo_root}",
                f"node|repo_entry|{repo_root}|",
                f"node|module|{repo_root}|",
            ),
            "knowledge": (f"knowledge|repo|{repo_root}|",),
        }

        for object_type in ("node", "knowledge"):
            for obj in self.object_repository.list(object_type):
                identity_key = str(obj.get("identity_key", ""))
                if not identity_key.startswith(identity_prefixes[object_type]):
                    continue
                if obj["id"] in expected_ids[object_type]:
                    continue
                if obj.get("status") == "archived":
                    continue
                operations.append(
                    PatchOperation(
                        op="archive_object",
                        object_type=object_type,
                        object_id=obj["id"],
                        changes={"reason": "repo_ingest_missing_from_latest_scan"},
                    )
                )
        return operations

    def _ingest_document(self, file_path: str | Path, kind: str, content_type: str) -> dict:
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"File path is not a file: {path}")
        text = path.read_text(encoding="utf-8")
        return self._ingest_text_source(
            identity=f"source|{kind}|{path}",
            kind=kind,
            title=path.name,
            origin={"path": str(path)},
            text=text,
            content_type=content_type,
            activity_kind="reading",
            artifact_ref=str(path),
        )

    def _ingest_text_source(
        self,
        identity: str,
        kind: str,
        title: str,
        origin: dict,
        text: str,
        content_type: str,
        activity_kind: str,
        artifact_ref: str,
    ) -> dict:
        timestamp = utc_now_iso()
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
        source_id = stable_id("src", identity)
        node_id = stable_id("node", f"node|document|{identity}")
        segments = self._document_segments(artifact_ref, text, content_type)

        source = Source(
            id=source_id,
            kind=kind,
            origin=origin,
            title=title,
            identity_key=identity,
            fingerprint=fingerprint,
            content_type=content_type,
            payload={
                "text": text,
                "byte_count": len(text.encode("utf-8")),
                "segment_count": len(segments),
            },
            segments=segments,
            metadata={"scanned_at": timestamp},
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        node = Node(
            id=node_id,
            kind="document",
            name=title,
            slug=slugify(title),
            identity_key=f"node|document|{identity}",
            aliases=[artifact_ref],
            summary=f"{content_type.title()} document with {len(segments)} source segments.",
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        activity = Activity(
            id=stable_id("act", f"activity|{kind}_ingest|{identity}|{fingerprint}"),
            kind=activity_kind,
            title=f"Ingest source: {title}",
            summary=f"Captured {title} as a {content_type} source.",
            identity_key=f"activity|{kind}_ingest|{identity}|{fingerprint}",
            status="finalized",
            started_at=timestamp,
            ended_at=timestamp,
            related_node_refs=[node.id],
            related_work_item_refs=[],
            source_refs=[source.id],
            produced_object_refs=[node.id],
            artifact_refs=[artifact_ref],
            created_at=timestamp,
            updated_at=timestamp,
        )
        operations = [
            self._upsert_operation(
                object_type="source",
                object_id=source.id,
                changes={
                    "kind": source.kind,
                    "origin": source.origin,
                    "title": source.title,
                    "identity_key": source.identity_key,
                    "fingerprint": source.fingerprint,
                    "content_type": source.content_type,
                    "payload": source.payload,
                    "segments": source.segments,
                    "metadata": source.metadata,
                    "status": source.status,
                    "created_at": source.created_at,
                    "updated_at": source.updated_at,
                },
            ),
            self._upsert_operation(
                object_type="node",
                object_id=node.id,
                changes={
                    "kind": node.kind,
                    "name": node.name,
                    "slug": node.slug,
                    "identity_key": node.identity_key,
                    "aliases": node.aliases,
                    "summary": node.summary,
                    "status": node.status,
                    "created_at": node.created_at,
                    "updated_at": node.updated_at,
                },
            ),
            self._upsert_operation(
                object_type="activity",
                object_id=activity.id,
                changes={
                    "kind": activity.kind,
                    "title": activity.title,
                    "summary": activity.summary,
                    "identity_key": activity.identity_key,
                    "status": activity.status,
                    "started_at": activity.started_at,
                    "ended_at": activity.ended_at,
                    "related_node_refs": activity.related_node_refs,
                    "related_work_item_refs": activity.related_work_item_refs,
                    "source_refs": activity.source_refs,
                    "produced_object_refs": activity.produced_object_refs,
                    "artifact_refs": activity.artifact_refs,
                    "created_at": activity.created_at,
                    "updated_at": activity.updated_at,
                },
            ),
        ]
        patch = MemoryPatch(
            id=new_id("patch"),
            source={"type": "system", "id": f"memory.ingest.{kind}", **origin},
            operations=operations,
            created_at=timestamp,
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "patch_id": apply_result.patch_id,
            "source_id": source.id,
            "node_id": node.id,
            "activity_id": activity.id,
            "segment_count": len(segments),
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
        }

    def _ingest_binary_stub(self, path: Path, kind: str, raw: bytes) -> dict:
        timestamp = utc_now_iso()
        fingerprint = hashlib.sha256(raw).hexdigest()
        identity = f"source|{kind}|{path}"
        source_id = stable_id("src", identity)
        source = Source(
            id=source_id,
            kind=kind,
            origin={"path": str(path)},
            title=path.name,
            identity_key=identity,
            fingerprint=fingerprint,
            content_type="binary_stub",
            payload={"path": str(path), "byte_count": len(raw), "sha256": fingerprint},
            segments=[],
            metadata={"scanned_at": timestamp},
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        operation = self._upsert_operation(
            object_type="source",
            object_id=source.id,
            changes={
                "kind": source.kind,
                "origin": source.origin,
                "title": source.title,
                "identity_key": source.identity_key,
                "fingerprint": source.fingerprint,
                "content_type": source.content_type,
                "payload": source.payload,
                "segments": source.segments,
                "metadata": source.metadata,
                "status": source.status,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
            },
        )
        patch = MemoryPatch(
            id=new_id("patch"),
            source={"type": "system", "id": f"memory.ingest.{kind}", "path": str(path)},
            operations=[operation],
            created_at=timestamp,
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "patch_id": apply_result.patch_id,
            "source_id": source.id,
            "node_id": None,
            "activity_id": None,
            "segment_count": 0,
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
        }

    def _document_segments(self, locator: str, text: str, content_type: str) -> list[SourceSegment]:
        if content_type == "markdown":
            chunks = self._markdown_chunks(text)
        else:
            chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        if not chunks and text.strip():
            chunks = [text.strip()]

        segments: list[SourceSegment] = []
        for index, chunk in enumerate(chunks[:100], start=1):
            title = chunk.splitlines()[0][:80]
            segment_id = slugify(f"{index}-{title}") or f"segment-{index}"
            segments.append(
                SourceSegment(
                    segment_id=segment_id,
                    locator={"kind": "source", "ref": locator, "segment_index": index},
                    excerpt=chunk[:800],
                    hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                )
            )
        return segments

    def _html_to_text(self, html: str) -> str:
        html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        html = re.sub(r"(?s)<[^>]+>", "\n", html)
        return re.sub(r"\n{3,}", "\n\n", html).strip()

    def _markdown_chunks(self, text: str) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if line.startswith("#") and current:
                chunks.append("\n".join(current).strip())
                current = [line]
                continue
            current.append(line)
        if current:
            chunks.append("\n".join(current).strip())
        return [chunk for chunk in chunks if chunk]
