from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_index: int
    kind: str
    title: str
    level: int
    heading_path: list[str]
    line_start: int
    line_end: int
    text: str
    excerpt: str


class DocumentChunker:
    """Split text documents into stable, citable chunks."""

    def __init__(self, max_chars: int = 1600, overlap_lines: int = 2, excerpt_chars: int = 1600) -> None:
        self.max_chars = max(200, max_chars)
        self.overlap_lines = max(0, overlap_lines)
        self.excerpt_chars = max(80, excerpt_chars)

    def chunk(self, text: str, content_type: str = "text") -> list[DocumentChunk]:
        if content_type == "markdown":
            return self.chunk_markdown(text)
        return self.chunk_text(text)

    def chunk_text(self, text: str) -> list[DocumentChunk]:
        lines = text.splitlines()
        if not lines:
            return []
        blocks: list[tuple[int, int]] = []
        start = 0
        for index, line in enumerate(lines):
            if line.strip():
                continue
            if start < index:
                blocks.append((start, index))
            start = index + 1
        if start < len(lines):
            blocks.append((start, len(lines)))
        if not blocks and text.strip():
            blocks = [(0, len(lines))]

        chunks: list[DocumentChunk] = []
        for start_row, end_row in blocks:
            chunks.extend(
                self._split_block(
                    lines=lines,
                    start_row=start_row,
                    end_row=end_row,
                    kind="paragraph",
                    title=self._first_nonempty_line(lines[start_row:end_row], fallback="Text"),
                    level=1,
                    heading_path=[],
                    next_index=len(chunks) + 1,
                )
            )
        return chunks

    def chunk_markdown(self, text: str) -> list[DocumentChunk]:
        lines = text.splitlines()
        if not lines:
            return []

        chunks: list[DocumentChunk] = []
        content_start = 0
        frontmatter_end = self._frontmatter_end(lines)
        if frontmatter_end is not None:
            chunks.extend(
                self._split_block(
                    lines=lines,
                    start_row=0,
                    end_row=frontmatter_end,
                    kind="frontmatter",
                    title="Frontmatter",
                    level=0,
                    heading_path=[],
                    next_index=len(chunks) + 1,
                )
            )
            content_start = frontmatter_end

        headings = self._markdown_headings(lines, start_row=content_start)
        if headings and content_start < headings[0]["row"]:
            chunks.extend(
                self._split_block(
                    lines=lines,
                    start_row=content_start,
                    end_row=headings[0]["row"],
                    kind="preamble",
                    title="Preamble",
                    level=1,
                    heading_path=[],
                    next_index=len(chunks) + 1,
                )
            )
        if not headings and content_start < len(lines):
            chunks.extend(
                self._split_block(
                    lines=lines,
                    start_row=content_start,
                    end_row=len(lines),
                    kind="section",
                    title="Document",
                    level=1,
                    heading_path=[],
                    next_index=len(chunks) + 1,
                )
            )
            return chunks

        for index, heading in enumerate(headings):
            end_row = headings[index + 1]["row"] if index + 1 < len(headings) else len(lines)
            chunks.extend(
                self._split_block(
                    lines=lines,
                    start_row=heading["row"],
                    end_row=end_row,
                    kind="section",
                    title=heading["title"],
                    level=heading["level"],
                    heading_path=heading["heading_path"],
                    next_index=len(chunks) + 1,
                )
            )
        return chunks

    def _split_block(
        self,
        lines: list[str],
        start_row: int,
        end_row: int,
        kind: str,
        title: str,
        level: int,
        heading_path: list[str],
        next_index: int,
    ) -> list[DocumentChunk]:
        block_lines = lines[start_row:end_row]
        if not "\n".join(block_lines).strip():
            return []

        chunks: list[DocumentChunk] = []
        current_start = start_row
        current_lines: list[str] = []
        fenced = False
        for row in range(start_row, end_row):
            line = lines[row]
            current_lines.append(line)
            marker = self._fence_marker(line)
            if marker:
                fenced = not fenced
            current_text = "\n".join(current_lines).strip()
            if len(current_text) < self.max_chars or fenced or row + 1 >= end_row:
                continue
            chunks.append(
                self._make_chunk(
                    chunk_index=next_index + len(chunks),
                    kind=kind,
                    title=title,
                    level=level,
                    heading_path=heading_path,
                    line_start=current_start + 1,
                    line_end=row + 1,
                    text=current_text,
                )
            )
            overlap_start = max(start_row, row + 1 - self.overlap_lines)
            current_start = overlap_start
            current_lines = lines[overlap_start : row + 1]

        remaining = "\n".join(current_lines).strip()
        if remaining:
            chunks.append(
                self._make_chunk(
                    chunk_index=next_index + len(chunks),
                    kind=kind,
                    title=title,
                    level=level,
                    heading_path=heading_path,
                    line_start=current_start + 1,
                    line_end=end_row,
                    text=remaining,
                )
            )
        return chunks

    def _make_chunk(
        self,
        chunk_index: int,
        kind: str,
        title: str,
        level: int,
        heading_path: list[str],
        line_start: int,
        line_end: int,
        text: str,
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_index=chunk_index,
            kind=kind,
            title=title,
            level=level,
            heading_path=list(heading_path),
            line_start=line_start,
            line_end=line_end,
            text=text,
            excerpt=text[: self.excerpt_chars],
        )

    def _frontmatter_end(self, lines: list[str]) -> int | None:
        if not lines or lines[0].strip() != "---":
            return None
        for index in range(1, min(len(lines), 200)):
            if lines[index].strip() in {"---", "..."}:
                return index + 1
        return None

    def _markdown_headings(self, lines: list[str], start_row: int) -> list[dict]:
        headings: list[dict] = []
        stack: list[tuple[int, str]] = []
        fenced = False
        for row in range(start_row, len(lines)):
            line = lines[row]
            marker = self._fence_marker(line)
            if marker:
                fenced = not fenced
                continue
            if fenced:
                continue
            parsed = self._heading(line)
            if parsed is None:
                continue
            level, title = parsed
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            headings.append(
                {
                    "row": row,
                    "level": level,
                    "title": title,
                    "heading_path": [entry[1] for entry in stack],
                }
            )
        return headings

    def _heading(self, line: str) -> tuple[int, str] | None:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            return None
        title = match.group(2).strip()
        if not title:
            return None
        return len(match.group(1)), title

    def _fence_marker(self, line: str) -> str | None:
        stripped = line.strip()
        if stripped.startswith("```"):
            return "```"
        if stripped.startswith("~~~"):
            return "~~~"
        return None

    def _first_nonempty_line(self, lines: list[str], fallback: str) -> str:
        for line in lines:
            if line.strip():
                return line.strip()[:80]
        return fallback
