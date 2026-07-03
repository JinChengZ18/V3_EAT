from __future__ import annotations

import argparse
import base64
import copy
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
SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)

MAP_SEARCH = """function onSearch(e){ const q=e.target.value.trim().toLowerCase(); if(!q) return;
  let best=-1; for(let s=0;s<D.states.length;s++){ if(D.states[s].n.toLowerCase().includes(q)){best=s;break;} }
  if(best>=0 && spans[best]){ zoomTo(spans[best]); } }"""

TIMELINE_SEARCH = """function onSearch(e){const q=e.target.value.trim().toLowerCase();if(!q)return;
  for(let s=0;s<D.states.length;s++)if(D.states[s].n.toLowerCase().includes(q)){
    if(spans[s])zoomTo(spans[s]);break;}}"""

PATCHED_SEARCH = """function normSearch(v){return (v==null?'':String(v)).normalize('NFKC').toLowerCase();}
function stateSearchText(s){return [s.n,s.b].concat(s.q||[]).map(normSearch).join('\\n');}
function onSearch(e){ const q=normSearch(e.target.value.trim()); if(!q) return;
  let best=-1; for(let s=0;s<D.states.length;s++){ if(stateSearchText(D.states[s]).includes(q)){best=s;break;} }
  if(best>=0 && spans[best]){ document.getElementById('continent').value='__world'; zoomTo(spans[best]); } }"""


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

CHROME_REPLACEMENTS = [
    ("<title>Regional Resource Map</title>", f"<title>{ZH_CHROME['Regional Resource Map']}</title>"),
    ("<h1>Regional Resource Map</h1>", f"<h1>{ZH_CHROME['Regional Resource Map']}</h1>"),
    ("<title>Resource Timeline</title>", f"<title>{ZH_CHROME['Resource Timeline']}</title>"),
    ("<h1>Resource Timeline</h1>", f"<h1>{ZH_CHROME['Resource Timeline']}</h1>"),
    ("<span>Resource layer</span>", f"<span>{ZH_CHROME['Resource layer']}</span>"),
    ("<span>Colormap</span>", f"<span>{ZH_CHROME['Colormap']}</span>"),
    ("<span>Continent</span>", f"<span>{ZH_CHROME['Continent']}</span>"),
    ("<span>Mode</span>", f"<span>{ZH_CHROME['Mode']}</span>"),
    ('aria-label="Mode"', f'aria-label="{ZH_CHROME["Mode"]}"'),
    ('placeholder="Search state…"', f'placeholder="{ZH_CHROME["Search state…"]}"'),
    (">Labels</span>", f">{ZH_CHROME['Labels']}</span>"),
    ('title="Theme" aria-label="Theme"', f'title="{ZH_CHROME["Theme"]}" aria-label="{ZH_CHROME["Theme"]}"'),
    ("<button id=\"reset\" class=\"btn\">Reset</button>", f"<button id=\"reset\" class=\"btn\">{ZH_CHROME['Reset']}</button>"),
    ('title="Reset" aria-label="Reset"', f'title="{ZH_CHROME["Reset"]}" aria-label="{ZH_CHROME["Reset"]}"'),
    ('title="Zoom in" aria-label="Zoom in"', f'title="{ZH_CHROME["Zoom in"]}" aria-label="{ZH_CHROME["Zoom in"]}"'),
    ('title="Zoom out" aria-label="Zoom out"', f'title="{ZH_CHROME["Zoom out"]}" aria-label="{ZH_CHROME["Zoom out"]}"'),
    (">no data</span>", f">{ZH_CHROME['no data']}</span>"),
    (">water</span>", f">{ZH_CHROME['water']}</span>"),
    (">Absolute</button>", f">{ZH_CHROME['Absolute']}</button>"),
    (">Δ vs previous</button>", f">{ZH_CHROME['Δ vs previous']}</button>"),
    (">Δ vs first</button>", f">{ZH_CHROME['Δ vs first']}</button>"),
    ('aria-label="Version"', f'aria-label="{ZH_CHROME["Version"]}"'),
]

SCRIPT_LITERAL_REPLACEMENTS = [
    ("wo.textContent='World'", f"wo.textContent='{ZH_CHROME['World']}'"),
    ('wo.textContent="World"', f'wo.textContent="{ZH_CHROME["World"]}"'),
]


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


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        value = str(value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _add_search_aliases(payload: dict, state_ids: list[str], game, ui) -> dict:
    if len(payload.get("states", [])) != len(state_ids):
        raise ValueError(f"state count mismatch: html={len(payload.get('states', []))} computed={len(state_ids)}")

    rows = {row.state_id: row for row in build_region_rows(game, ui)}
    for item, state_id in zip(payload["states"], state_ids):
        row = rows.get(state_id)
        bucket = ui[f"rbucket_{row.bucket or 'other'}"] if row is not None else ""
        localized = game.loc.get_clean(state_id) if game.loc is not None else state_id
        aliases = _dedupe([state_id, localized, bucket])
        aliases = [alias for alias in aliases if alias not in {item.get("n", ""), item.get("b", "")}]
        if aliases:
            item["q"] = aliases
        else:
            item.pop("q", None)
    return payload


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


def _patch_interactions(html: str, label_max_px: int) -> str:
    label_re = re.compile(
        rf"(?m)^(\s*)let sz=L\.sz\*z; if\(sz<8\*dpr\) continue; sz=Math\.min\(sz,{label_max_px}\*dpr\);"
    )
    html, label_count = label_re.subn(
        rf"\1const zr=Math.max(1,z/minZ());\n\1let sz=Math.max(10*dpr,Math.min({label_max_px}*dpr,L.sz*Math.sqrt(zr)*dpr));",
        html,
        count=1,
    )
    if label_count != 1:
        raise ValueError("label zoom expression not found")

    if MAP_SEARCH in html:
        return html.replace(MAP_SEARCH, PATCHED_SEARCH, 1)
    if TIMELINE_SEARCH in html:
        return html.replace(TIMELINE_SEARCH, PATCHED_SEARCH, 1)
    raise ValueError("search handler not found")


def _translate_chrome_segment(segment: str) -> str:
    for src, dst in CHROME_REPLACEMENTS:
        segment = segment.replace(src, dst)
    return segment


def _translate_script_literals(open_tag: str, body: str, close_tag: str) -> str:
    if 'id="data"' in open_tag:
        return open_tag + body + close_tag
    for src, dst in SCRIPT_LITERAL_REPLACEMENTS:
        body = body.replace(src, dst)
    return open_tag + body + close_tag


def _translate_chrome(html: str) -> str:
    parts = []
    pos = 0
    for match in SCRIPT_RE.finditer(html):
        parts.append(_translate_chrome_segment(html[pos : match.start()]))
        parts.append(_translate_script_literals(match.group(1), match.group(2), match.group(3)))
        pos = match.end()
    parts.append(_translate_chrome_segment(html[pos:]))
    return "".join(parts)


def _translate_html(html: str, payload: dict) -> str:
    html = _replace_payload(html, payload)
    html = re.sub(r'<html lang="[^"]*"', '<html lang="zh-CN"', html, count=1)
    return _translate_chrome(html)


def publish_one(src: Path, dst_en: Path, dst_zh: Path, game_en, game_zh, game_root: Path, label_max_px: int) -> None:
    html = src.read_text(encoding="utf-8")
    state_ids = _state_ids(game_en, game_root, get_ui("english"), html)

    payload = _payload(html)
    en_payload = _add_search_aliases(copy.deepcopy(payload), state_ids, game_zh, get_ui("simp_chinese"))
    en_html = _patch_interactions(_replace_payload(html, en_payload), label_max_px).replace("\r\n", "\n")
    dst_en.write_text(en_html, encoding="utf-8", newline="\n")

    zh_payload = _translate_payload(copy.deepcopy(payload), state_ids, game_zh, get_ui("simp_chinese"))
    zh_payload = _add_search_aliases(zh_payload, state_ids, game_en, get_ui("english"))
    zh_html = _patch_interactions(_translate_html(html, zh_payload), label_max_px).replace("\r\n", "\n")
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

    publish_one(map_src, out_dir / "resource_map.html", out_dir / "resource_map.zh.html", game_en, game_zh, game_root, 26)
    publish_one(
        timeline_src,
        out_dir / "resource_timeline.html",
        out_dir / "resource_timeline.zh.html",
        game_en,
        game_zh,
        game_root,
        24,
    )
    # Keep the entry page source controlled by docs/showcase/index.html; this
    # script only publishes the content pages from existing map artifacts.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
