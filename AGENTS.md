# AGENTS.md

## Codebase search (important)

- Prefer the `semantic_search` tool for exploring this codebase.
- Call `semantic_search` first for any "where is ...", "find ...", or "how does ... work" question. It searches the project's vector index and returns ranked code chunks with file path, start/end line and the chunk text.
- Only fall back to `grep` / `glob` / `read` when you need an exact literal match, a file by name, or to read a file that `semantic_search` already located.
- Do not enumerate the repository with `bash` (`Get-ChildItem`, `dir`, `find`, ...) to locate code; use `semantic_search` or `grep` / `glob` instead.

## File paths (important)

- Copy file paths verbatim from tool output (`glob`, `read`, `semantic_search`); never hand-type or "fix" an absolute Windows path.
- Do not mix `/` and `\` separators in a path. Prefer workspace-relative paths (e.g. `fold-epub/web/src/main.js`) for files inside the workspace.
- For files outside the workspace root, first locate them with `glob` in that directory and use the exact returned path.
- If a tool reports "File not found", do not retry the same path; run `glob` first and use its result.
