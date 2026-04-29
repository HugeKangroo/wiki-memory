# Source Extraction Dependency Decision

Date: 2026-04-29

Memory Substrate should not add PDF, DOCX, XLSX, OCR, or multimodal captioning packages as core dependencies yet.

Current decision:

- Keep source extraction behind `memory_ingest` adapters.
- Keep canonical memory objects independent of document parser packages.
- Use the shared `document_chunker.v1` contract after text is available.
- Treat PDF/DOCX/XLSX extraction packages as adapter-specific choices that require evidence from real source-capture failures.
- Treat image OCR/captioning as optional evidence capture for document-heavy workflows, not as a memory-core requirement.
- Defer source deletion and cascade cleanup semantics until source manifests and provenance policy are explicit.

Rationale:

- The current product core is durable memory governance, retrieval, evidence, graph/index projection, and agent-facing MCP ergonomics.
- Heavy extraction libraries expand install and failure surface before the project has enough source-ingest pressure to justify them.
- If extraction packages are added later, their output should flow into source segments with locators and hashes; they should not change canonical storage semantics.

Candidate future adapter packages to evaluate only when needed:

- PDF: `pymupdf`, `pypdf`, or `unstructured` depending on whether layout, tables, or plain text are required.
- DOCX: `python-docx` for structured Word documents.
- XLSX/CSV: `openpyxl` for workbook structure, stdlib `csv` for plain CSV.
- OCR/images: `pytesseract`, local vision models, or hosted captioning only behind explicit optional adapters.
