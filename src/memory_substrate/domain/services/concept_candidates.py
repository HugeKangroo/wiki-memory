from __future__ import annotations

import re
from typing import Any


class ConceptCandidateDiscovery:
    """Find advisory concept candidates from canonical sources and memories."""

    _BACKTICK_RE = re.compile(r"`([^`\n]{2,80})`")
    _TITLE_PHRASE_RE = re.compile(
        r"\b(?:[A-Z][A-Za-z0-9]+|[A-Z]{2,})(?:[\s/-]+(?:[A-Z][A-Za-z0-9]+|[A-Z]{2,})){1,5}\b"
    )
    _CJK_RE = re.compile(
        r"[\u4e00-\u9fff]{0,8}(?:知识图谱|记忆系统|向量数据库|图数据库|概念候选|策略检索|知识沉淀|证据链|生命周期|上下文包)[\u4e00-\u9fff]{0,4}"
    )
    _LEADING_STOP_WORDS = {"a", "an", "and", "the", "this", "that", "these", "those"}
    _STOP_TERMS = {
        "api",
        "architecture",
        "background",
        "configuration",
        "content",
        "example",
        "examples",
        "guide",
        "implementation",
        "index",
        "installation",
        "intro",
        "introduction",
        "notes",
        "overview",
        "readme",
        "reference",
        "references",
        "setup",
        "summary",
        "test",
        "tests",
        "todo",
        "usage",
    }
    _STOP_KEYS = {
        "bugfixes",
        "callexamples",
        "contenttype",
        "endfile",
    }
    _DOC_ARTIFACT_SUFFIXES = {"examples", "reference", "references", "todo", "usage"}

    def discover(
        self,
        *,
        sources: list[dict[str, Any]],
        knowledge_items: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
        source_ids: set[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return advisory candidates for concepts that may deserve durable memory."""
        existing_concepts = self._existing_concept_keys(knowledge_items, nodes)
        source_scope_refs = self._source_scope_refs_by_id(sources, nodes)
        buckets: dict[str, dict[str, Any]] = {}

        for source in sources:
            source_id = str(source.get("id", ""))
            if source_ids is not None and source_id not in source_ids:
                continue
            self._collect_source_terms(buckets, source, scope_refs=source_scope_refs.get(source_id, [source_id]))

        for item in knowledge_items:
            if str(item.get("kind", "")) == "concept":
                continue
            if source_ids is not None and not self._knowledge_refs_sources(item, source_ids):
                continue
            self._collect_knowledge_terms(buckets, item)

        candidates = [
            self._candidate_from_bucket(bucket)
            for normalized_key, bucket in buckets.items()
            if normalized_key not in existing_concepts and self._has_enough_support(bucket)
        ]
        candidates.sort(key=lambda item: (-item["score"], item["title"], item["normalized_key"]))
        return candidates[:limit]

    def _collect_source_terms(self, buckets: dict[str, dict[str, Any]], source: dict[str, Any], *, scope_refs: list[str]) -> None:
        source_id = str(source.get("id", ""))
        source_title_key = self._normalize_key(str(source.get("title", "")))
        for segment in source.get("segments", []) or []:
            if not isinstance(segment, dict):
                continue
            segment_id = str(segment.get("segment_id", ""))
            locator = segment.get("locator", {})
            if not self._is_top_level_title_locator(locator):
                for heading in self._heading_terms(locator):
                    if self._normalize_key(heading) == source_title_key:
                        continue
                    self._add(
                        buckets,
                        heading,
                        reason="heading_path",
                        source_id=source_id,
                        segment_id=segment_id,
                        locator=locator,
                        scope_refs=scope_refs,
                    )
            for term in self._extract_terms(str(segment.get("excerpt", ""))):
                self._add(
                    buckets,
                    term,
                    reason="source_excerpt",
                    source_id=source_id,
                    segment_id=segment_id,
                    locator=locator,
                    scope_refs=scope_refs,
                )

    def _collect_knowledge_terms(self, buckets: dict[str, dict[str, Any]], item: dict[str, Any]) -> None:
        object_id = str(item.get("id", ""))
        object_ref = {"object_type": "knowledge", "object_id": object_id}
        scope_refs = self._knowledge_scope_refs(item)
        for term in self._extract_terms(f"{item.get('title', '')}\n{item.get('summary', '')}"):
            self._add(buckets, term, reason="knowledge_text", object_ref=object_ref, scope_refs=scope_refs)

    def _heading_terms(self, locator: Any) -> list[str]:
        if not isinstance(locator, dict):
            return []
        headings = locator.get("heading_path", [])
        if isinstance(headings, str):
            headings = [headings]
        if not isinstance(headings, list):
            return []
        if not headings:
            return []
        return self._extract_terms(str(headings[-1]), include_whole=True)

    def _is_top_level_title_locator(self, locator: Any) -> bool:
        if not isinstance(locator, dict):
            return False
        line_start = locator.get("line_start")
        headings = locator.get("heading_path", [])
        return line_start == 1 and isinstance(headings, list) and len(headings) == 1

    def _extract_terms(self, text: str, *, include_whole: bool = False) -> list[str]:
        terms: list[str] = []
        if include_whole:
            terms.append(text)
        terms.extend(match.group(1) for match in self._BACKTICK_RE.finditer(text))
        terms.extend(match.group(0) for match in self._TITLE_PHRASE_RE.finditer(text))
        terms.extend(match.group(0) for match in self._CJK_RE.finditer(text))
        return [term for term in (self._clean_title(term) for term in terms) if self._is_valid_term(term)]

    def _add(
        self,
        buckets: dict[str, dict[str, Any]],
        title: str,
        *,
        reason: str,
        source_id: str | None = None,
        segment_id: str | None = None,
        locator: Any = None,
        object_ref: dict[str, str] | None = None,
        scope_refs: list[str] | None = None,
    ) -> None:
        normalized_key = self._normalize_key(title)
        if not normalized_key:
            return
        bucket = buckets.setdefault(
            normalized_key,
            {
                "title": title,
                "normalized_key": normalized_key,
                "occurrences": 0,
                "reasons": set(),
                "evidence_refs": {},
                "object_refs": {},
                "scope_refs": {},
            },
        )
        bucket["occurrences"] += 1
        bucket["reasons"].add(reason)
        if source_id and segment_id:
            bucket["evidence_refs"].setdefault(
                (source_id, segment_id),
                {"source_id": source_id, "segment_id": segment_id, "locator": locator},
            )
        if object_ref:
            bucket["object_refs"].setdefault((object_ref["object_type"], object_ref["object_id"]), object_ref)
        for scope_ref in scope_refs or []:
            bucket["scope_refs"].setdefault(str(scope_ref), str(scope_ref))

    def _has_enough_support(self, bucket: dict[str, Any]) -> bool:
        support_count = len(bucket["evidence_refs"]) + len(bucket["object_refs"])
        if bucket["occurrences"] < 2:
            return False
        if support_count >= 2:
            return True
        return "heading_path" in bucket["reasons"] and support_count >= 1

    def _candidate_from_bucket(self, bucket: dict[str, Any]) -> dict[str, Any]:
        source_count = len({item["source_id"] for item in bucket["evidence_refs"].values()})
        evidence_refs = sorted(
            bucket["evidence_refs"].values(),
            key=lambda item: (item["source_id"], item["segment_id"]),
        )[:5]
        object_refs = sorted(
            bucket["object_refs"].values(),
            key=lambda item: (item["object_type"], item["object_id"]),
        )[:5]
        support_count = len(bucket["evidence_refs"]) + len(bucket["object_refs"])
        score = min(1.0, 0.35 + 0.08 * bucket["occurrences"] + 0.12 * support_count + 0.08 * source_count)
        confidence = min(0.85, 0.45 + 0.05 * bucket["occurrences"] + 0.08 * support_count)
        scope_refs = sorted(bucket["scope_refs"]) or [item["source_id"] for item in evidence_refs[:1]]
        suggested_input = {
            "kind": "concept",
            "title": bucket["title"],
            "summary": (
                f"Candidate concept '{bucket['title']}'. Review the cited evidence and replace this summary with "
                "a bounded durable definition before writing."
            ),
            "reason": f"Agent reviewed candidate concept '{bucket['title']}' from repeated source evidence and judged it durable.",
            "memory_source": "agent_inferred",
            "scope_refs": scope_refs,
            "evidence_refs": evidence_refs,
            "payload": {
                "candidate": {
                    "normalized_key": bucket["normalized_key"],
                    "occurrences": bucket["occurrences"],
                    "source_count": source_count,
                    "support_count": support_count,
                    "reasons": sorted(bucket["reasons"]),
                }
            },
            "status": "candidate",
            "confidence": round(confidence, 3),
        }
        return {
            "kind": "concept_candidate",
            "title": bucket["title"],
            "normalized_key": bucket["normalized_key"],
            "score": round(score, 3),
            "occurrences": bucket["occurrences"],
            "source_count": source_count,
            "support_count": support_count,
            "evidence_refs": evidence_refs,
            "object_refs": object_refs,
            "reasons": sorted(bucket["reasons"]),
            "suggested_memory": {
                "mode": "knowledge",
                "kind": "concept",
                "title": bucket["title"],
                "status": "candidate",
                "confidence": round(confidence, 3),
                "input_data": suggested_input,
                "editable_fields": ["summary", "reason", "scope_refs", "payload"],
                "summary_prompt": "Write a bounded reusable definition from the cited evidence before remembering.",
            },
            "review_guidance": self._review_guidance(),
            "next_actions": [
                "review_and_remember",
                "attach_evidence_refs",
                "skip_if_project_specific_noise",
            ],
        }

    def _knowledge_refs_sources(self, item: dict[str, Any], source_ids: set[str]) -> bool:
        for evidence_ref in item.get("evidence_refs", []) or []:
            if isinstance(evidence_ref, dict) and str(evidence_ref.get("source_id")) in source_ids:
                return True
        return False

    def _existing_concept_keys(self, knowledge_items: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> set[str]:
        keys: set[str] = set()
        for item in knowledge_items:
            if str(item.get("kind", "")) != "concept" or str(item.get("status", "")) in {"archived", "superseded"}:
                continue
            key = self._normalize_key(str(item.get("title", "")))
            if key:
                keys.add(key)
        for node in nodes:
            if str(node.get("kind", "")) != "concept" or str(node.get("status", "")) in {"archived", "superseded"}:
                continue
            for name in [node.get("name"), node.get("title"), *(node.get("aliases", []) or [])]:
                key = self._normalize_key(str(name or ""))
                if key:
                    keys.add(key)
        return keys

    def _source_scope_refs_by_id(self, sources: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> dict[str, list[str]]:
        nodes_by_identity = {
            str(node.get("identity_key", "")): str(node.get("id", ""))
            for node in nodes
            if node.get("identity_key") and node.get("id")
        }
        refs: dict[str, list[str]] = {}
        for source in sources:
            source_id = str(source.get("id", ""))
            source_identity = str(source.get("identity_key", ""))
            node_identity = ""
            if source_identity.startswith("source|repo|"):
                node_identity = source_identity.replace("source|repo|", "node|repo|", 1)
            elif source_identity:
                node_identity = f"node|document|{source_identity}"
            node_id = nodes_by_identity.get(node_identity)
            refs[source_id] = [node_id] if node_id else [source_id]
        return refs

    def _knowledge_scope_refs(self, item: dict[str, Any]) -> list[str]:
        scope_refs = [str(ref) for ref in item.get("scope_refs", []) if ref]
        if scope_refs:
            return scope_refs
        subject_refs = [str(ref) for ref in item.get("subject_refs", []) if ref]
        if subject_refs:
            return subject_refs
        return [str(item["id"])] if item.get("id") else []

    def _review_guidance(self) -> dict[str, Any]:
        return {
            "required_checks": [
                "read_evidence_refs",
                "query_existing_memory_for_title_and_synonyms",
                "choose_scope_refs_before_write",
                "rewrite_summary_from_evidence",
            ],
            "outcomes": [
                {
                    "action": "remember_as_concept",
                    "when": "the candidate names a reusable abstraction with stable meaning",
                    "tool": "memory_remember",
                    "mode": "knowledge",
                    "kind": "concept",
                    "input_data": "suggested_memory.input_data",
                },
                {
                    "action": "remember_as_procedure",
                    "when": "the evidence describes a reusable ordered workflow or rule of operation",
                    "tool": "memory_remember",
                    "mode": "knowledge",
                    "kind": "procedure",
                },
                {
                    "action": "remember_as_decision",
                    "when": "the evidence records a selected direction, tradeoff, or rejected alternative",
                    "tool": "memory_remember",
                    "mode": "knowledge",
                    "kind": "decision",
                },
                {
                    "action": "merge_with_existing",
                    "when": "query finds an existing memory with the same meaning",
                    "tool": "memory_remember_or_memory_maintain",
                },
                {
                    "action": "skip_candidate",
                    "when": "the term is a project title, generic heading, temporary task phrase, or weakly evidenced",
                    "tool": None,
                },
            ],
        }

    def _clean_title(self, term: str) -> str:
        cleaned = re.sub(r"\s+", " ", term.strip(" \t\r\n`*_#:-")).strip()
        words = cleaned.split()
        while words and words[0].lower() in self._LEADING_STOP_WORDS:
            words = words[1:]
        return " ".join(words)

    def _is_valid_term(self, term: str) -> bool:
        if not term:
            return False
        lowered = term.lower()
        if lowered in self._STOP_TERMS:
            return False
        if self._normalize_key(term) in self._STOP_KEYS:
            return False
        if self._looks_like_document_artifact_title(term):
            return False
        if len(term) > 80:
            return False
        if any(character.isalpha() for character in term):
            alpha_words = [word for word in re.split(r"[\s/-]+", term) if any(char.isalpha() for char in word)]
            return len(alpha_words) >= 2 or bool(re.search(r"[\u4e00-\u9fff]", term))
        return False

    def _normalize_key(self, term: str) -> str:
        cleaned = self._clean_title(term).lower()
        return "".join(character for character in cleaned if character.isalnum())

    def _looks_like_document_artifact_title(self, term: str) -> bool:
        words = [word.lower() for word in re.split(r"[\s/-]+", term) if word]
        return len(words) >= 2 and words[-1] in self._DOC_ARTIFACT_SUFFIXES
