from __future__ import annotations

import re
from typing import Any


class ConceptCandidateDiscovery:
    """Find advisory concept candidates from canonical sources and memories."""

    _BACKTICK_RE = re.compile(r"`([^`\n]{2,80})`")
    _TITLE_PHRASE_RE = re.compile(
        r"\b(?:[A-Z][A-Za-z0-9]+|[A-Z]{2,})(?:[\s/-]+(?:[A-Z][A-Za-z0-9]+|[A-Z]{2,})){1,5}\b"
    )
    _TOOL_MODE_RE = re.compile(r"\bmemory_[a-z_]+(?:\s+[a-z_]+)?\b")
    _COMMAND_PREFIXES = {"mempalace", "memory-substrate", "codex", "claude"}
    _COMMAND_PHRASE_RE = re.compile(
        r"\b(?:mempalace|memory-substrate|codex|claude)\s+[a-z][a-z0-9_-]*"
        r"(?:\s+--?[a-z][a-z0-9_-]*(?:=[^\s`.,;:)]+)?){0,3}\b"
    )
    _FORMAT_MARKER_RE = re.compile(r"\b[a-z]{2}-[a-z]{2}\b")
    _FILE_EXTENSION_RE = re.compile(
        r"\.(?:c|cc|cpp|css|go|h|hpp|html|java|js|json|jsx|lock|md|py|rs|toml|ts|tsx|txt|yaml|yml)\b",
        re.IGNORECASE,
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
        "mandatoryoutputlanguage",
        "newfeatures",
        "writtenbefore",
        "yyyymmdd",
    }
    _ACTION_PHRASE_VERBS = {
        "builds",
        "converts",
        "creates",
        "displays",
        "evaluates",
        "generates",
        "includes",
        "loads",
        "manages",
        "parses",
        "provides",
        "queries",
        "reads",
        "returns",
        "runs",
        "saves",
        "stores",
        "supports",
        "tracks",
        "uses",
        "writes",
    }
    _SHORTCUT_MARKERS = {"alt", "cmd", "ctrl", "esc", "shift"}
    _DOC_ARTIFACT_SUFFIXES = {"examples", "features", "reference", "references", "tasks", "todo", "usage"}
    _PATH_PREFIXES = {
        ".codex",
        ".github",
        ".worktrees",
        "build",
        "dist",
        "docs",
        "memory",
        "node_modules",
        "src",
        "tests",
    }
    _TEMPORARY_TASK_KEYS = {
        "activeexecutionqueue",
        "currentfocus",
        "currentpriority",
        "currentpriorityorder",
        "executionconstraints",
        "inprogress",
        "nextaction",
        "nextactions",
        "nextstep",
        "nextsteps",
        "openquestion",
        "openquestions",
        "scratchnote",
        "scratchnotes",
        "temporaryexecutionstate",
        "temporarytaskvocabulary",
        "workinprogress",
    }

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
        return self.analyze(
            sources=sources,
            knowledge_items=knowledge_items,
            nodes=nodes,
            source_ids=source_ids,
            limit=limit,
        )["candidates"]

    def analyze(
        self,
        *,
        sources: list[dict[str, Any]],
        knowledge_items: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
        source_ids: set[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Return candidates plus diagnostics for advisory concept discovery."""
        existing_concepts = self._existing_concept_keys(knowledge_items, nodes)
        source_scope_refs = self._source_scope_refs_by_id(sources, nodes)
        buckets: dict[str, dict[str, Any]] = {}
        skipped: dict[str, dict[str, Any]] = {}

        for source in sources:
            source_id = str(source.get("id", ""))
            if source_ids is not None and source_id not in source_ids:
                continue
            self._collect_source_terms(
                buckets,
                source,
                skipped=skipped,
                scope_refs=source_scope_refs.get(source_id, [source_id]),
            )

        for item in knowledge_items:
            if str(item.get("kind", "")) == "concept":
                continue
            if source_ids is not None and not self._knowledge_refs_sources(item, source_ids):
                continue
            self._collect_knowledge_terms(buckets, item, skipped=skipped)

        candidates = [
            self._candidate_from_bucket(bucket)
            for normalized_key, bucket in buckets.items()
            if normalized_key not in existing_concepts and self._has_enough_support(bucket)
        ]
        candidates.sort(key=lambda item: (-item["score"], item["title"], item["normalized_key"]))
        diagnostics = self._candidate_diagnostics(skipped)
        diagnostics["counts"]["eligible"] = len(candidates)
        diagnostics["counts"]["returned"] = min(len(candidates), limit)
        return {
            "candidates": candidates[:limit],
            "candidate_diagnostics": diagnostics,
        }

    def _collect_source_terms(
        self,
        buckets: dict[str, dict[str, Any]],
        source: dict[str, Any],
        *,
        skipped: dict[str, dict[str, Any]],
        scope_refs: list[str],
    ) -> None:
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
            self._record_skipped_terms(skipped, str(segment.get("excerpt", "")))
            for heading in self._raw_heading_terms(locator):
                if self._normalize_key(heading) == source_title_key:
                    continue
                self._record_skipped_terms(skipped, heading, include_whole=True)

    def _collect_knowledge_terms(
        self,
        buckets: dict[str, dict[str, Any]],
        item: dict[str, Any],
        *,
        skipped: dict[str, dict[str, Any]],
    ) -> None:
        object_id = str(item.get("id", ""))
        object_ref = {"object_type": "knowledge", "object_id": object_id}
        scope_refs = self._knowledge_scope_refs(item)
        text = f"{item.get('title', '')}\n{item.get('summary', '')}"
        for term in self._extract_terms(text):
            self._add(buckets, term, reason="knowledge_text", object_ref=object_ref, scope_refs=scope_refs)
        self._record_skipped_terms(skipped, text)

    def _heading_terms(self, locator: Any) -> list[str]:
        return [
            term
            for heading in self._raw_heading_terms(locator)
            for term in self._extract_terms(heading, include_whole=True)
        ]

    def _raw_heading_terms(self, locator: Any) -> list[str]:
        if not isinstance(locator, dict):
            return []
        headings = locator.get("heading_path", [])
        if isinstance(headings, str):
            headings = [headings]
        if not isinstance(headings, list):
            return []
        if not headings:
            return []
        return [str(headings[-1])]

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
        terms.extend(match.group(0) for match in self._TOOL_MODE_RE.finditer(text))
        terms.extend(match.group(0) for match in self._COMMAND_PHRASE_RE.finditer(text))
        terms.extend(match.group(0) for match in self._FORMAT_MARKER_RE.finditer(text))
        terms.extend(match.group(0) for match in self._CJK_RE.finditer(text))
        return [term for term in (self._clean_title(term) for term in terms) if self._is_valid_term(term)]

    def _record_skipped_terms(self, skipped: dict[str, dict[str, Any]], text: str, *, include_whole: bool = False) -> None:
        terms: list[str] = []
        if include_whole:
            terms.append(text)
        terms.extend(match.group(1) for match in self._BACKTICK_RE.finditer(text))
        terms.extend(match.group(0) for match in self._TITLE_PHRASE_RE.finditer(text))
        terms.extend(match.group(0) for match in self._TOOL_MODE_RE.finditer(text))
        terms.extend(match.group(0) for match in self._COMMAND_PHRASE_RE.finditer(text))
        terms.extend(match.group(0) for match in self._FORMAT_MARKER_RE.finditer(text))
        terms.extend(match.group(0) for match in self._CJK_RE.finditer(text))
        for raw_term in terms:
            term = self._clean_title(raw_term)
            reason = self._skip_reason(term)
            if not reason:
                continue
            normalized_key = self._normalize_key(term)
            if not normalized_key:
                continue
            entry = skipped.setdefault(
                normalized_key,
                {"title": term, "normalized_key": normalized_key, "reason": reason, "occurrences": 0},
            )
            entry["occurrences"] += 1

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
        classification = self._classify_candidate(bucket)
        ranking_signals = self._ranking_signals(bucket, classification)
        raw_score = (
            0.28
            + min(0.24, 0.04 * bucket["occurrences"])
            + min(0.24, 0.08 * support_count)
            + min(0.12, 0.06 * source_count)
        )
        score = max(0.0, min(1.0, raw_score + ranking_signals["score_adjustment"]))
        confidence = min(0.85, 0.45 + 0.05 * bucket["occurrences"] + 0.08 * support_count)
        scope_refs = sorted(bucket["scope_refs"]) or [item["source_id"] for item in evidence_refs[:1]]
        recommendation = self._candidate_recommendation(
            classification=classification,
            ranking_signals=ranking_signals,
            score=score,
            source_count=source_count,
            support_count=support_count,
        )
        suggested_input = {
            "kind": classification["suggested_kind"],
            "title": bucket["title"],
            "summary": (
                f"Candidate {classification['candidate_type']} '{bucket['title']}'. Review the cited evidence and replace this summary with "
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
            "candidate_type": classification["candidate_type"],
            "title": bucket["title"],
            "normalized_key": bucket["normalized_key"],
            "score": round(score, 3),
            "occurrences": bucket["occurrences"],
            "source_count": source_count,
            "support_count": support_count,
            "evidence_refs": evidence_refs,
            "object_refs": object_refs,
            "reasons": sorted(bucket["reasons"]),
            "ranking_signals": ranking_signals,
            "recommendation": recommendation,
            "suggested_memory": {
                "mode": "knowledge",
                "kind": classification["suggested_kind"],
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

    def _classify_candidate(self, bucket: dict[str, Any]) -> dict[str, str]:
        title = str(bucket["title"])
        lower = title.lower()
        if self._looks_like_memory_tool_mode(title) or self._looks_like_command_phrase(title) or self._looks_like_schema_fragment(title):
            return {"candidate_type": "implementation_detail", "suggested_kind": "concept"}
        if self._looks_like_tool_or_library(title):
            return {"candidate_type": "tool_library", "suggested_kind": "concept"}
        if any(marker in lower for marker in ("workflow", "process", "procedure", "protocol", "lifecycle", "pipeline")):
            return {"candidate_type": "procedure", "suggested_kind": "procedure"}
        if lower.startswith(("use ", "adopt ", "choose ", "select ", "prefer ")) or "decision" in lower:
            return {"candidate_type": "decision", "suggested_kind": "decision"}
        if any(marker in lower for marker in ("jsonl", "content-type", "file format", "config")):
            return {"candidate_type": "implementation_detail", "suggested_kind": "concept"}
        return {"candidate_type": "concept", "suggested_kind": "concept"}

    def _ranking_signals(self, bucket: dict[str, Any], classification: dict[str, str]) -> dict[str, Any]:
        bonuses: list[str] = []
        penalties: list[str] = []
        title = str(bucket["title"])
        lower = title.lower()
        adjustment = 0.0
        if classification["candidate_type"] in {"concept", "procedure", "decision"}:
            bonuses.append("durable_memory_candidate")
            adjustment += 0.08
        if classification["candidate_type"] == "procedure":
            bonuses.append("workflow_or_process")
            adjustment += 0.04
        if any(marker in lower for marker in ("principle", "design", "architecture", "memory", "wiki")):
            bonuses.append("core_abstraction_term")
            adjustment += 0.06
        if classification["candidate_type"] == "tool_library":
            penalties.append("tool_or_library_name")
            adjustment -= 0.22
            if len(bucket["scope_refs"]) <= 1:
                penalties.append("single_scope_tool_or_library")
                adjustment -= 0.04
        if classification["candidate_type"] == "implementation_detail":
            penalties.append("implementation_detail")
            adjustment -= 0.2
        if any(character.isdigit() for character in title) or "/" in title:
            penalties.append("version_or_package_marker")
            adjustment -= 0.04
        return {"bonuses": bonuses, "penalties": penalties, "score_adjustment": round(adjustment, 3)}

    def _candidate_recommendation(
        self,
        *,
        classification: dict[str, str],
        ranking_signals: dict[str, Any],
        score: float,
        source_count: int,
        support_count: int,
    ) -> dict[str, Any]:
        candidate_type = classification["candidate_type"]
        why = list(ranking_signals.get("bonuses", []))
        why.extend(ranking_signals.get("penalties", []))
        if source_count >= 2:
            why.append("cross_source_support")
        if support_count >= 3:
            why.append("repeated_evidence_support")

        if candidate_type in {"concept", "procedure", "decision"} and score >= 0.65:
            priority = "high"
            action = "review_for_durable_memory"
            recommended = True
        elif candidate_type in {"concept", "procedure", "decision"}:
            priority = "medium"
            action = "review_for_durable_memory"
            recommended = True
        else:
            priority = "low"
            action = "review_only_if_current_task_needs_it"
            recommended = False

        return {
            "priority": priority,
            "recommended": recommended,
            "recommended_action": action,
            "why": why[:6],
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
        return self._skip_reason(term) is None

    def _normalize_key(self, term: str) -> str:
        cleaned = self._clean_title(term).lower()
        return "".join(character for character in cleaned if character.isalnum())

    def _looks_like_document_artifact_title(self, term: str) -> bool:
        words = [word.lower() for word in re.split(r"[\s/-]+", term) if word]
        return len(words) >= 2 and words[-1] in self._DOC_ARTIFACT_SUFFIXES

    def _looks_like_tool_or_library(self, term: str) -> bool:
        lower = term.lower()
        return (
            "/" in term
            or lower.endswith(("-mcp", " mcp"))
            or lower.startswith(("claude code", "lm studio", "openai", "neo4j", "kuzu", "lancedb", "bge"))
            or any(marker in lower for marker in ("embedding model", "jsonl", "sdk", "api"))
        )

    def _looks_like_memory_tool_mode(self, term: str) -> bool:
        return bool(re.search(r"\bmemory_[a-z_]+(?:\s+[a-z_]+)?\b", term))

    def _looks_like_command_phrase(self, term: str) -> bool:
        words = [word for word in re.split(r"[\s]+", term.strip()) if word]
        if len(words) < 2 or len(words) > 5:
            return False
        if words[0].lower() in self._COMMAND_PREFIXES:
            command_like = re.fullmatch(r"[a-z][a-z0-9_-]*", words[1]) and all(
                re.fullmatch(r"(?:[a-z][a-z0-9_-]*|--?[a-z][a-z0-9_-]*(?:=[^\s`]+)?)", word)
                for word in words[2:]
            )
            return bool(command_like)
        command_like = words[0].islower() and all(re.fullmatch(r"[a-z][a-z0-9_-]*", word) for word in words)
        return bool(command_like)

    def _looks_like_schema_fragment(self, term: str) -> bool:
        lower = term.lower()
        return any(marker in lower for marker in (" not null", " primary key", " foreign key", " varchar", " integer"))

    def _looks_like_action_phrase(self, term: str) -> bool:
        words = [word.lower() for word in re.split(r"[\s/-]+", term.strip()) if word]
        return len(words) >= 2 and words[0] in self._ACTION_PHRASE_VERBS

    def _looks_like_shortcut_marker(self, term: str) -> bool:
        words = {word.lower() for word in re.split(r"[\s/+:-]+", term.strip()) if word}
        return bool(words & self._SHORTCUT_MARKERS)

    def _looks_like_path_fragment(self, term: str) -> bool:
        stripped = term.strip()
        if not stripped:
            return False
        lower = stripped.lower()
        if lower.startswith(("./", "../", "/", "~/")) or "\\" in stripped:
            return True
        path_parts = [part for part in re.split(r"[/\\]+", stripped) if part]
        if len(path_parts) >= 3:
            return True
        if len(path_parts) >= 2 and path_parts[0].lower() in self._PATH_PREFIXES:
            return True
        if self._FILE_EXTENSION_RE.search(stripped):
            return True
        return False

    def _looks_like_temporary_task_vocabulary(self, term: str) -> bool:
        normalized_key = self._normalize_key(term)
        if normalized_key in self._TEMPORARY_TASK_KEYS:
            return True
        words = [word.lower() for word in re.split(r"[\s/-]+", term.strip()) if word]
        if len(words) < 2 or len(words) > 4:
            return False
        if words[0] in {"active", "current", "next", "open", "pending", "temporary"} and words[-1] in {
            "action",
            "actions",
            "focus",
            "item",
            "items",
            "order",
            "priority",
            "question",
            "questions",
            "state",
            "step",
            "steps",
            "task",
            "tasks",
        }:
            return True
        return False

    def _skip_reason(self, term: str) -> str | None:
        if not term:
            return "empty"
        lowered = term.lower()
        if lowered in self._STOP_TERMS:
            return "generic_term"
        if self._normalize_key(term) in self._STOP_KEYS:
            return "document_artifact"
        if self._looks_like_document_artifact_title(term):
            return "document_artifact"
        if self._looks_like_path_fragment(term):
            return "path_fragment"
        if self._looks_like_temporary_task_vocabulary(term):
            return "temporary_task_vocabulary"
        if self._looks_like_format_marker(term):
            return "format_marker"
        if self._looks_like_action_phrase(term):
            return "action_phrase"
        if self._looks_like_shortcut_marker(term):
            return "shortcut_marker"
        if len(term) > 80:
            return "too_long"
        if any(character.isalpha() for character in term):
            alpha_words = [word for word in re.split(r"[\s/-]+", term) if any(char.isalpha() for char in word)]
            if len(alpha_words) >= 2 or bool(re.search(r"[\u4e00-\u9fff]", term)):
                return None
        return "weak_term"

    def _candidate_diagnostics(self, skipped: dict[str, dict[str, Any]]) -> dict[str, Any]:
        entries = sorted(skipped.values(), key=lambda item: (-item["occurrences"], item["title"]))[:20]
        skipped_by_reason: dict[str, int] = {}
        examples_by_reason: dict[str, list[str]] = {}
        for item in skipped.values():
            reason = str(item["reason"])
            skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1
            examples = examples_by_reason.setdefault(reason, [])
            if len(examples) < 5:
                examples.append(str(item["title"]))
        noise_classes = [
            {"reason": reason, "count": skipped_by_reason[reason], "examples": examples_by_reason.get(reason, [])}
            for reason in sorted(skipped_by_reason, key=lambda key: (-skipped_by_reason[key], key))
        ]
        return {
            "skipped": entries,
            "skipped_by_reason": skipped_by_reason,
            "noise_classes": noise_classes,
            "counts": {
                "skipped": len(skipped),
                "returned": 0,
            },
        }

    def _looks_like_format_marker(self, term: str) -> bool:
        return bool(re.fullmatch(r"[a-z]{2}-[a-z]{2}", term.lower()))
