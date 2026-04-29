from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FrontmatterParseResult:
    metadata: dict[str, Any]
    body: str
    warnings: list[str] = field(default_factory=list)


def render_frontmatter(metadata: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_format_scalar(item)}")
            continue
        lines.append(f"{key}: {_format_scalar(value)}")
    return "\n".join(lines)


def split_frontmatter(markdown: str) -> FrontmatterParseResult:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return FrontmatterParseResult(metadata={}, body=markdown, warnings=[])

    closing_index = None
    for index in range(1, min(len(lines), 500)):
        if lines[index].strip() in {"---", "..."}:
            closing_index = index
            break
    if closing_index is None:
        return FrontmatterParseResult(
            metadata={},
            body=markdown,
            warnings=["unclosed_frontmatter_fallback_to_body"],
        )

    metadata, warnings = _parse_frontmatter_lines(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :])
    if markdown.endswith("\n"):
        body += "\n"
    return FrontmatterParseResult(metadata=metadata, body=body, warnings=warnings)


def _parse_frontmatter_lines(lines: list[str]) -> tuple[dict[str, Any], list[str]]:
    metadata: dict[str, Any] = {}
    warnings: list[str] = []
    current_list_key: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key:
            value = _parse_scalar(stripped[2:].strip())
            bucket = metadata.setdefault(current_list_key, [])
            if isinstance(bucket, list):
                bucket.append(value)
            continue
        current_list_key = None
        if ":" not in line:
            warnings.append(f"ignored_malformed_frontmatter_line:{stripped[:40]}")
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            warnings.append(f"ignored_invalid_frontmatter_key:{key[:40]}")
            continue
        raw_value = raw_value.strip()
        if not raw_value:
            metadata[key] = []
            current_list_key = key
            continue
        metadata[key] = _parse_scalar(raw_value)
    return metadata, warnings


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _parse_scalar(value: str) -> Any:
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
