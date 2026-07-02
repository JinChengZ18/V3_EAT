#!/usr/bin/env bash
#
# Regenerate the full Feature-2b map gallery into out/regions/maps/.
# Exercises every `regions map…` command + option once, bucketed into subfolders.
#
# Usage:
#   bash scripts/gen_maps.sh                 # default (auto-detects the V3 install)
#   PYTHON=py bash scripts/gen_maps.sh       # use a different Python launcher
#   GAME_ROOT="D:/Games/Victoria 3" bash scripts/gen_maps.sh   # force the game path
#
# Windows: run it from Git Bash (ships with Git for Windows). The commands are
# just `python -m v3_eat …`, so a PowerShell user can equally copy them by hand.
#
# Outputs go under out/regions/ (git-ignored), plus docs/showcase/ for the
# GitHub Pages preview.

set -uo pipefail
cd "$(dirname "$0")/.."                       # project root (scripts/..)

PY="${PYTHON:-python}"
M="out/regions/maps"
DOCS_SHOWCASE="docs/showcase"
OLD="baseline_regions_v1.0.6.xlsx"            # bundled baselines (baselines/ is auto-searched)
NEW="baseline_regions_v1.13.8.xlsx"           # oldest -> newest span for the diff demos
TL=(baseline_regions_v1.0.6.xlsx baseline_regions_v1.3.6.xlsx \
    baseline_regions_v1.6.2.xlsx baseline_regions_v1.9.8.xlsx \
    baseline_regions_v1.13.8.xlsx)            # full chronological chain for the timeline
GR=(); [ "${GAME_ROOT:-}" ] && GR=(--game-root "$GAME_ROOT")

run() { echo; echo ">>> $*"; "$@" || echo "    (command failed — continuing)"; }

echo "== V3_EAT Feature 2b — regenerating all maps into $M/ =="

# 1. Gallery: every layer as PNG + vector SVG, plus the interactive HTML viewer
run "$PY" -m v3_eat regions map --all --svg "${GR[@]}"

# 2. Crop-distribution maps (16 crops) -> maps/crops/
run "$PY" -m v3_eat regions map --crops --svg "${GR[@]}"

# 3. 1836 national borders on every layer (civilized filter) -> maps/national/
run "$PY" -m v3_eat regions map --all --countries --svg --format png --out "$M/national" "${GR[@]}"

# 4. Recognized-only national borders -> maps/national_recognized/
run "$PY" -m v3_eat regions map --metric total_capacity --countries --country-filter recognized \
    --svg --format png --out "$M/national_recognized" "${GR[@]}"

# 5. High-res showcase (native 8192 + borders + SVG + interactive HTML) -> maps/showcase/
run "$PY" -m v3_eat regions map --metric total_capacity --full-res --countries --svg \
    --format both --out "$M/showcase" "${GR[@]}"

# 6. Option demos (grid+cmap, log+no-borders, gamma+reverse) -> maps/options/
run "$PY" -m v3_eat regions map --metric building_coal_mine --grid --cmap magma \
    --svg --format png --out "$M/options" "${GR[@]}"
run "$PY" -m v3_eat regions map --metric building_gold_mine --log-scale --no-borders \
    --svg --format png --out "$M/options" "${GR[@]}"
run "$PY" -m v3_eat regions map --metric building_iron_mine --gamma 1.0 --reverse --cmap viridis \
    --svg --format png --out "$M/options" "${GR[@]}"

# 7. Cross-version change maps -> maps/diffs/
run "$PY" -m v3_eat regions map-diff "$OLD" "$NEW" --metric building_coal_mine --countries --svg "${GR[@]}"
run "$PY" -m v3_eat regions map-diff "$OLD" "$NEW" --metric total_capacity --svg "${GR[@]}"
run "$PY" -m v3_eat regions map-diff "$OLD" "$NEW" --metric building_iron_mine --svg "${GR[@]}"
# building_oil_rig was "石油精炼厂" in 1.0.6 — exercises the cross-version rename match
run "$PY" -m v3_eat regions map-diff "$OLD" "$NEW" --metric building_oil_rig --svg "${GR[@]}"

# 8. Multi-version timeline viewer — full 1.0.6 -> 1.13.8 chain (+ a no-current variant)
run "$PY" -m v3_eat regions map-timeline "${TL[@]}" "${GR[@]}"
run "$PY" -m v3_eat regions map-timeline "${TL[@]}" --no-current \
    --out "$M/timeline_nocurrent" "${GR[@]}"

# 9. Excel region report with the map atlas embedded
run "$PY" -m v3_eat regions report --maps --out report_regions_with_maps.xlsx "${GR[@]}"

# 10. GitHub Pages showcase HTML (tracked docs artifacts, smaller than the local full-res app)
run "$PY" -m v3_eat regions map --format html --html-width 2400 --out "$DOCS_SHOWCASE" "${GR[@]}"
run "$PY" -m v3_eat regions map-timeline "${TL[@]}" --width 1800 --out "$DOCS_SHOWCASE" "${GR[@]}"

echo
echo "== Done =="
echo "   $M/                  gallery PNG/SVG + resource_map.html + resource_timeline.html"
echo "   $M/crops/            16 crop-distribution maps"
echo "   $M/national/         national borders on every layer"
echo "   $M/diffs/            cross-version change maps"
echo "   $M/showcase/         native-8192 showcase + resource_map.html"
echo "   $M/options/ national_recognized/ timeline_nocurrent/   option variants"
echo "   out/regions/reports/report_regions_with_maps.xlsx       Excel + embedded atlas"
echo "   $DOCS_SHOWCASE/index.html              GitHub Pages bilingual preview entry"
echo "   $DOCS_SHOWCASE/resource_map.html       GitHub Pages resource map artifact"
echo "   $DOCS_SHOWCASE/resource_timeline.html  GitHub Pages timeline artifact"
