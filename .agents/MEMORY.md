# V3_EAT Agent Memory

## Orientation

- Repo root is `V3_EAT`; parent directories contain the Victoria 3 install and should not be edited for this project.
- Durable project rules live in `CLAUDE.md`.
- Agent coordination notes belong here rather than in user-facing docs.

## 2026-07-03

- Added project memory from `D:/Backups/Claude/CLAUDE-20260702.md`, scoped to V3_EAT.
- GitHub Pages requires one-time Settings > Pages > Build and deployment > Source > GitHub Actions before workflow deployment. Keep Pages actions on Node 24-compatible major versions.
- GitHub Pages showcase entry is `docs/showcase/index.html`; it switches between `resource_map.html`/`resource_timeline.html` and their `.zh.html` content versions. Do not separately regenerate the docs timeline; publish existing `out/regions/maps` HTML with `scripts/publish_showcase.py` so map and timeline style/resolution stay aligned.
