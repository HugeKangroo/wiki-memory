from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.domain.services.document_chunker import DocumentChunker


class DocumentChunkerTest(unittest.TestCase):
    def test_markdown_preserves_frontmatter_code_fences_tables_and_cjk(self) -> None:
        text = (
            "---\n"
            "title: 复利记忆\n"
            "---\n\n"
            "# Guide\n\n"
            "中文记忆系统说明。\n\n"
            "```python\n"
            "# Not a heading\n"
            "print('x')\n"
            "```\n\n"
            "| Name | Value |\n"
            "| --- | --- |\n"
            "| 复利 | 记忆 |\n\n"
            "## Use\n\n"
            "调用 MCP tools。\n"
        )

        chunks = DocumentChunker(max_chars=400).chunk_markdown(text)

        frontmatter = chunks[0]
        guide = next(chunk for chunk in chunks if chunk.title == "Guide")
        use = next(chunk for chunk in chunks if chunk.title == "Use")

        self.assertEqual(frontmatter.kind, "frontmatter")
        self.assertEqual((frontmatter.line_start, frontmatter.line_end), (1, 3))
        self.assertIn("title: 复利记忆", frontmatter.text)
        self.assertIn("# Not a heading", guide.text)
        self.assertIn("| 复利 | 记忆 |", guide.text)
        self.assertEqual(guide.heading_path, ["Guide"])
        self.assertEqual(use.heading_path, ["Guide", "Use"])
        self.assertGreater(use.line_start, guide.line_start)

    def test_markdown_splits_oversized_sections_with_line_overlap(self) -> None:
        lines = ["# Long"] + [f"line {index} " + ("x" * 20) for index in range(20)]
        chunks = DocumentChunker(max_chars=220, overlap_lines=2).chunk_markdown("\n".join(lines))

        self.assertGreater(len(chunks), 1)
        self.assertEqual({chunk.title for chunk in chunks}, {"Long"})
        self.assertLessEqual(chunks[1].line_start, chunks[0].line_end)
        self.assertIn("line", chunks[1].text)


if __name__ == "__main__":
    unittest.main()
