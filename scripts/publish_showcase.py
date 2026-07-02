from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from v3_eat.analysis.regions import build_region_rows
from v3_eat.game_root import find_game_root
from v3_eat.i18n import get_ui
from v3_eat.loader import load
from v3_eat.map.metrics import LEGACY_REMOVED_LOC, _loc_name, build_crop_metrics, build_metrics
from v3_eat.map.render import ProvinceIndex
DATA_RE = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)
IMG_RE = re.compile(r"data:image/png;base64,([A-Za-z0-9+/=]+)")


ZH_CHROME = {
    "Regional Resource Map": "地区资源地图",
    "Resource Timeline": "资源时间线",
    "Resource layer": "资源图层",
    "Colormap": "配色",
    "Continent": "大洲",
    "Search state…": "搜索地区…",
    "Search state": "搜索地区",
    "Labels": "数值标注",
    "Reset": "全图",
    "World": "全世界",
    "no data": "无数据",
    "water": "水域",
    "Mode": "模式",
    "Version": "版本",
    "Absolute": "绝对值",
    "Δ vs previous": "相对上一版",
    "Δ vs first": "相对首版",
    "(current)": "（当前）",
    "Zoom in": "放大",
    "Zoom out": "缩小",
    "Theme": "主题",
}


def _embedded_width(html: str) -> int:
    match = IMG_RE.search(html)
    if not match:
        raise ValueError("embedded base image not found")
    raw = base64.b64decode(match.group(1))
    with Image.open(io.BytesIO(raw)) as img:
        return int(img.width)


def _replace_payload(html: str, payload: dict) -> str:
    match = DATA_RE.search(html)
    if not match:
        raise ValueError("payload script not found")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return html[:match.start()] + match.group(1) + data + match.group(3) + html[match.end():]


def _payload(html: str) -> dict:
    match = DATA_RE.search(html)
    if not match:
        raise ValueError("payload script not found")
    return json.loads(match.group(2))


def _state_ids(game, game_root: Path, ui, html: str) -> list[str]:
    width = _embedded_width(html)
    rows = list(build_region_rows(game, ui))
    index = ProvinceIndex.build(game, game_root, width=width)
    return [row.state_id for row in rows if row.state_id in index.state_to_colors]


def _metric_labels(game, ui) -> dict[str, str]:
    rows = list(build_region_rows(game, ui))
    labels = {
        metric.key: metric.label
        for metric in build_metrics(game, ui, rows=rows, include_aggregates=True, include_resources=True)
    }
    labels.update({metric.key: metric.label for metric in build_crop_metrics(game, ui)})
    for kind, loc_key in LEGACY_REMOVED_LOC.items():
        labels[f"legacy_{kind}"] = _loc_name(game, loc_key)
    return labels


def _translate_payload(payload: dict, state_ids: list[str], game_zh, ui_zh) -> dict:
    rows_zh = {row.state_id: row for row in build_region_rows(game_zh, ui_zh)}
    if len(payload.get("states", [])) != len(state_ids):
        raise ValueError(f"state count mismatch: html={len(payload.get('states', []))} computed={len(state_ids)}")

    for item, state_id in zip(payload["states"], state_ids):
        item["n"] = game_zh.loc.get_clean(state_id) if game_zh.loc is not None else state_id
        row = rows_zh.get(state_id)
        item["b"] = ui_zh[f"rbucket_{row.bucket or 'other'}"] if row is not None else item.get("b", "")

    labels = _metric_labels(game_zh, ui_zh)
    for metric in payload.get("metrics", []):
        metric["label"] = labels.get(metric.get("key"), metric.get("label", ""))

    if "versions" in payload:
        payload["versions"] = [str(v).replace("(current)", "（当前）") for v in payload["versions"]]
    return payload


def _translate_html(html: str, payload: dict) -> str:
    html = _replace_payload(html, payload)
    html = re.sub(r'<html lang="[^"]*"', '<html lang="zh-CN"', html, count=1)
    for src, dst in ZH_CHROME.items():
        html = html.replace(src, dst)
    return html


def publish_one(src: Path, dst_en: Path, dst_zh: Path, game_en, game_zh, game_root: Path) -> None:
    html = src.read_text(encoding="utf-8")
    dst_en.write_text(html.replace("\r\n", "\n"), encoding="utf-8", newline="\n")

    payload = _payload(html)
    state_ids = _state_ids(game_en, game_root, get_ui("english"), html)
    zh_payload = _translate_payload(payload, state_ids, game_zh, get_ui("simp_chinese"))
    zh_html = _translate_html(html, zh_payload).replace("\r\n", "\n")
    dst_zh.write_text(zh_html, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish existing out/regions/maps HTML files to docs/showcase.")
    parser.add_argument("--maps-dir", type=Path, default=ROOT / "out" / "regions" / "maps")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "showcase")
    parser.add_argument("--game-root", type=Path, default=None)
    args = parser.parse_args()

    maps_dir = args.maps_dir if args.maps_dir.is_absolute() else ROOT / args.maps_dir
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    map_src = maps_dir / "resource_map.html"
    timeline_src = maps_dir / "resource_timeline.html"
    for path in (map_src, timeline_src):
        if not path.exists():
            raise FileNotFoundError(path)

    game_root = find_game_root(args.game_root)
    game_en = load(game_root, "english")
    game_zh = load(game_root, "simp_chinese")

    publish_one(map_src, out_dir / "resource_map.html", out_dir / "resource_map.zh.html", game_en, game_zh, game_root)
    publish_one(
        timeline_src,
        out_dir / "resource_timeline.html",
        out_dir / "resource_timeline.zh.html",
        game_en,
        game_zh,
        game_root,
    )
    # Keep the entry page source controlled by docs/showcase/index.html; this
    # script only publishes the content pages from existing map artifacts.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
