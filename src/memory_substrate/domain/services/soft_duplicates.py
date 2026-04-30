from __future__ import annotations

import re


SOFT_DUPLICATE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "to",
    "with",
}


class KnowledgeSoftDuplicateDetector:
    """Deterministic advisory duplicate detector for unstructured knowledge."""

    def possible_duplicates(self, candidate: dict, existing_items: list[dict], limit: int = 5) -> list[dict]:
        if self._structured_signature(candidate) is not None:
            return []
        candidates: list[dict] = []
        for item in existing_items:
            if item.get("status") in {"contested", "superseded", "archived"}:
                continue
            if self._structured_signature(item) is not None:
                continue
            if not self._scopes_overlap(item, candidate):
                continue
            score, reasons = self._score(item, candidate)
            if score < 0.5:
                continue
            candidates.append(
                {
                    "object_id": item["id"],
                    "score": round(score, 3),
                    "reasons": reasons,
                    "title": item.get("title", item["id"]),
                    "kind": item.get("kind", "knowledge"),
                    "status": item.get("status", "candidate"),
                }
            )
        candidates.sort(key=lambda entry: (-entry["score"], entry["title"], entry["object_id"]))
        return candidates[:limit]

    def groups(self, items: list[dict]) -> list[dict]:
        active_items = [item for item in items if item.get("status") not in {"contested", "superseded", "archived"}]
        groups: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for index, item in enumerate(active_items):
            for other in active_items[index + 1 :]:
                key = tuple(sorted((str(item["id"]), str(other["id"]))))
                if key in seen:
                    continue
                seen.add(key)
                matches = self.possible_duplicates(other, [item], limit=1)
                if not matches:
                    continue
                match = matches[0]
                groups.append(
                    {
                        "object_ids": [item["id"], other["id"]],
                        "score": match["score"],
                        "reasons": match["reasons"],
                    }
                )
        groups.sort(key=lambda group: (-group["score"], group["object_ids"]))
        return groups

    def _structured_signature(self, item: dict) -> tuple[str, str] | None:
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            return None
        subject_refs = item.get("subject_refs", [])
        subject = subject_refs[0] if subject_refs else payload.get("subject")
        predicate = payload.get("predicate")
        if not subject or not predicate:
            return None
        return (str(subject), str(predicate))

    def _scope_refs(self, item: dict) -> list[str]:
        scope_refs = item.get("scope_refs", [])
        if scope_refs:
            return [str(ref) for ref in scope_refs]
        payload = item.get("payload", {})
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        metadata_scope_refs = metadata.get("scope_refs", []) if isinstance(metadata, dict) else []
        return [str(ref) for ref in metadata_scope_refs]

    def _scopes_overlap(self, left: dict, right: dict) -> bool:
        left_scopes = set(self._scope_refs(left))
        right_scopes = set(self._scope_refs(right))
        if not left_scopes or not right_scopes:
            return True
        return bool(left_scopes.intersection(right_scopes))

    def _score(self, existing: dict, candidate: dict) -> tuple[float, list[str]]:
        reasons: list[str] = []
        title_overlap = self._token_overlap(str(existing.get("title", "")), str(candidate.get("title", "")))
        summary_overlap = self._token_overlap(str(existing.get("summary", "")), str(candidate.get("summary", "")))
        subject_overlap = self._list_overlap(existing.get("subject_refs", []), candidate.get("subject_refs", []))
        evidence_overlap = self._evidence_overlap(existing.get("evidence_refs", []), candidate.get("evidence_refs", []))
        kind_match = str(existing.get("kind", "")) == str(candidate.get("kind", ""))

        if title_overlap >= 0.3:
            reasons.append("title_overlap")
        if summary_overlap >= 0.25:
            reasons.append("summary_overlap")
        if kind_match:
            reasons.append("same_kind")
        if subject_overlap:
            reasons.append("shared_subject")
        if evidence_overlap:
            reasons.append("shared_evidence")

        score = (0.4 * title_overlap) + (0.4 * summary_overlap)
        if kind_match:
            score += 0.1
        if subject_overlap:
            score += 0.1
        if evidence_overlap:
            score += 0.1
        return min(score, 1.0), reasons

    def _token_overlap(self, left: str, right: str) -> float:
        left_tokens = self._tokens(left)
        right_tokens = self._tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens.intersection(right_tokens)) / len(left_tokens.union(right_tokens))

    def _tokens(self, value: str) -> set[str]:
        tokens: set[str] = set()
        for token in re.findall(r"[\w\u4e00-\u9fff]+", value.lower()):
            if token in SOFT_DUPLICATE_STOPWORDS:
                continue
            if token.isascii() and token.endswith("s") and len(token) > 3:
                token = token[:-1]
            tokens.add(token)
        return tokens

    def _list_overlap(self, left, right) -> bool:
        if not isinstance(left, list) or not isinstance(right, list):
            return False
        return bool({str(item) for item in left}.intersection(str(item) for item in right))

    def _evidence_overlap(self, left, right) -> bool:
        if not isinstance(left, list) or not isinstance(right, list):
            return False

        def key(evidence: dict) -> tuple[str, str] | None:
            if not isinstance(evidence, dict):
                return None
            source_id = str(evidence.get("source_id") or "")
            segment_id = str(evidence.get("segment_id") or "")
            if not source_id or not segment_id:
                return None
            return (source_id, segment_id)

        left_keys = {item for item in (key(evidence) for evidence in left) if item is not None}
        right_keys = {item for item in (key(evidence) for evidence in right) if item is not None}
        return bool(left_keys.intersection(right_keys))
