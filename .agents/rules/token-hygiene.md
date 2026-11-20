---
trigger: always_on
description: "Keep context and token usage lean across file reads, shell commands, and responses."
---

# Token Hygiene Rules

Keep context usage lean across tool calls and turns:

1. **Targeted Reads:** Skip generated, vendor, and cache paths (`frontend/node_modules/`, `frontend/dist/`, `package-lock.json`, `__pycache__/`, `.pytest_cache/`, `coses_varies/`). For large files, read only the needed `StartLine`–`EndLine` range. Never re-read unchanged files already in context.
2. **Bounded Command Output:** Keep terminal output compact:
   - Run targeted tests during iteration (`pytest tests/test_<module>.py -q --tb=short`), and run the full suite once before finishing (`pytest tests/ -q --tb=short`).
   - Prefer `git status -s` and `git diff --stat` (or path-scoped diffs) over full uncompressed dumps.
   - Limit directory listings and log queries (e.g., `-Depth 2`, `Select-Object -First 30`).
3. **Batching & Surgical Edits:** Batch independent reads, searches, and edits in parallel in a single turn. Use `edit_file` for targeted diffs instead of rewriting entire files.
4. **Concise Output & Session Hygiene:** Do not echo large file contents or raw command outputs already visible in tool results. Start a fresh conversation (or use `/compact`) when switching to an unrelated task or when context approaches 70%+.
