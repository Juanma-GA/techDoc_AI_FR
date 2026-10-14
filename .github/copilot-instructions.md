# Repository Search Strategy

When exploring an unfamiliar codebase:

1. Use `sgrep` first for semantic discovery when function, class, or file names are unknown.
2. Use `fd` to locate files matching likely names or extensions.
3. Use `rg` (ripgrep) for exact symbol, string, regex, or identifier search.
4. After discovering relevant files, read the smallest possible set of files before answering.
5. Prefer evidence from source code over assumptions.

Search order:

- Unknown concept → sgrep
- Known filename → fd
- Known identifier/string → rg

Examples:

Semantic search:
```bash
sgrep "where are PDFs converted into images" .
sgrep "OCR pipeline entry point" .
sgrep "authentication and authorization workflow" .
sgrep "Excel export generation" .
```

File discovery: 
```bash
fd ocr
fd auth
fd excel
```

Exact search:
```bash
rg "process_document"
rg "AuthenticationManager"
rg "export_to_excel"
```