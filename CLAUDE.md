# V3_EAT Project Memory

## Operating Rules

- Work inside this repository root; the surrounding Victoria 3 install directory is not the project.
- Do not push by default. Commit locally when useful, and push only when the user explicitly asks in the current turn.
- Keep user-facing docs and deliverables separate from agent coordination files. Put agent memory and coordination notes in `.agents/`.
- Use ASCII paths and file names for new files.
- Keep Markdown paragraphs and list items on one physical line unless tables, lists, or code blocks require structure.
- Preserve LF line endings and avoid Windows CRLF churn in diffs.
- Treat generated artifacts as generated: update sources or scripts first, then regenerate outputs.
- After writing or generating files, verify file existence and key content.
- Report failed, skipped, or unverified checks honestly.
- Use `J.C.` for map signatures or watermarks unless the user requests otherwise.

## GitHub Pages

- Pages source must be enabled once in repository Settings > Pages > Build and deployment > Source > GitHub Actions. The default `GITHUB_TOKEN` can deploy an existing Pages site but cannot create or enable it for the first time.
- Pages workflow actions should stay on Node 24-compatible major versions: `actions/checkout@v5`, `actions/configure-pages@v6`, `actions/upload-pages-artifact@v5`, and `actions/deploy-pages@v5`.

## Memory Updates

- Record durable cross-agent notes in `.agents/MEMORY.md`.
