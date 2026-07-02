# V3_EAT Agent Memory

## Orientation

- Repo root is `V3_EAT`; parent directories contain the Victoria 3 install and should not be edited for this project.
- Durable project rules live in `CLAUDE.md`.
- Agent coordination notes belong here rather than in user-facing docs.

## 2026-07-03

- Added project memory from `D:/Backups/Claude/CLAUDE-20260702.md`, scoped to V3_EAT.
- GitHub Pages requires one-time Settings > Pages > Build and deployment > Source > GitHub Actions before workflow deployment. Keep Pages actions on Node 24-compatible major versions.
- GitHub Pages showcase entry is `docs/showcase/index.html`; it embeds `resource_map.html` and `resource_timeline.html` and provides page plus Chinese/English UI switching. `scripts/gen_maps.sh` refreshes both tracked preview artifacts.
