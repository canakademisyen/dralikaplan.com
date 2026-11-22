"""Build the static dralikaplan.com site.

Usage: python3 tools/build_site.py            (writes into the project folder)
       python3 tools/build_site.py <src> <out>
Publications come from content/publications.json (see tools/fetch_publications.py).
"""
import hashlib
import json
import os
import re
import shutil
import sys
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tools", "campus-map-source.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "dist")
STATIC = os.path.join(ROOT, "static")  # files copied into the site as they are (photo, ...)
DOMAIN = "dralikaplan.com"
L = open(SRC, encoding="utf-8").read().split("\n")

def file_version(path):
    """Short content hash used as ?v= so browsers fetch a file again whenever it changes."""
    try:
        return hashlib.sha1(open(path, "rb").read()).hexdigest()[:8]
    except OSError:
        return "0"


PHOTO_V = file_version(os.path.join(STATIC, "assets", "ali-kaplan.jpg"))

PUBS_FILE = os.path.join(ROOT, "content", "publications.json")
PUBS = json.load(open(PUBS_FILE, encoding="utf-8")) if os.path.exists(PUBS_FILE) else {"works": []}

SITE = "https://dralikaplan.com"
NAME = "Ali KAPLAN"
YEAR = "2026"

# key, slug, title, building, colour, hit polygons, page lead
SECTIONS = [
    ("research", "research", "Research Papers", "Management of Nursing", "#7F77DD",
     ["807.6,251.9 929.5,181.5 1081.9,269.5 1081.9,467.5 960,537.9 807.6,449.9"],
     "Peer-reviewed articles on nursing management, lean healthcare and digital health."),
    ("projects", "projects", "Projects", "Research Labs", "#7F77DD",
     ["1102.9,523.6 1217.2,457.6 1398.2,562.1 1398.2,658.9 1283.9,724.9 1102.9,620.4"],
     "Funded and ongoing research projects, with my role and the teams I work with."),
    ("teaching", "teaching", "Teaching", "Faculty", "#378ADD",
     ["1390.6,690 1506.8,616 1666.9,708.4 1666.9,796.4 1552.5,862.4 1390.6,770"],
     "Courses I teach at Çanakkale Onsekiz Mart University and the training programmes I deliver."),
    ("books", "books", "Books", "Library", "#1D9E75",
     ["592.3,484 691.4,426.8 836.2,510.4 836.2,611.6 737.1,668.8 592.3,585.2"],
     "Books I have written or edited, and the chapters I have contributed."),
    ("talks", "talks", "Workshop & Talks", "Conference Hall", "#D85A30",
     ["870.5,679.8 981,616 1171.5,726 1171.5,796.4 1061,860.2 870.5,750.2"],
     "Conference presentations, invited talks and the workshops I run."),
    ("scicomm", "science-communication", "Science Communication", "My Home", "#639922",
     ["422.7,782.1 590.4,685.3 876.2,850.3 876.2,870.1 708.5,966.9 422.7,801.9",
      "535.1,763.4 615.2,700 721.9,765 721.9,836 641.8,882.2 535.1,820.6"],
     "Blog posts, interviews and media work that bring research to a wider audience."),
]

# ---------------------------------------------------------------- map SVG
# Static copy of the design: shapes are lines 583..1086, label bubbles follow.
shapes = "\n".join(L[582:1086])
labels_src = "\n".join(L[1086:1128])
groups = re.findall(r"<g>\n(.*?)\n</g>", labels_src, re.S)
assert len(groups) == 6, len(groups)

# The template loads Inter only for the "H" and "P" signs: use system sans instead.
shapes = shapes.replace('font-family="Inter, sans-serif"', 'font-family="system-ui, sans-serif"')


def minify_svg(s):
    s = re.sub(r"></(polygon|line|ellipse|circle|path|rect)>", "/>", s)
    s = re.sub(r"\s*\n\s*", "", s)
    return s


hits, tags = [], []
for (key, slug, title, building, color, polys, _lead), g in zip(SECTIONS, groups):
    g = g.replace("<path ", '<path class="tip" ', 1)
    label = html.escape(f"{title} – {building}")
    poly = "".join(f'<polygon class="hl" points="{p}"/>' for p in polys)
    hits.append(f'<a href="{slug}/" class="k-{key}" style="--c:{color}" tabindex="-1" aria-hidden="true">{poly}</a>')
    tags.append(f'<a href="{slug}/" class="k-{key} tag-link" style="--c:{color}" aria-label="{label}"><g class="tag">{g}</g></a>')

svg = (
    '<svg class="map" viewBox="405 135 1335 935" preserveAspectRatio="xMidYMid meet" '
    'role="group" aria-label="Isometric hospital campus map. Each building opens a section of the site.">'
    + minify_svg(shapes) + minify_svg("".join(hits)) + minify_svg("".join(tags)) + "</svg>"
)

# --------------------------------------------------------------- shared bits
FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" '
    "media=\"print\" onload=\"this.media='all'\">"
    '<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap"></noscript>'
)
FAVICON = (
    "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='8' fill='%232F3B55'/%3E%3Ctext x='16' y='22' text-anchor='middle' "
    "font-family='Georgia,serif' font-weight='700' font-size='16' fill='%23fff'%3EAK%3C/text%3E%3C/svg%3E\">"
)
SPECULATION = (
    '<script type="speculationrules">{"prerender":[{"where":{"href_matches":"/*"},"eagerness":"moderate"}]}</script>'
)


def head(title, desc, path, extra=""):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f'<meta name="description" content="{html.escape(desc)}">'
        f'<link rel="canonical" href="{SITE}{path}">'
        '<meta name="theme-color" content="#EAF4F1">'
        f'<meta property="og:type" content="website"><meta property="og:title" content="{html.escape(title)}">'
        f'<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{SITE}{path}">'
        + FAVICON + FONT + extra + SPECULATION + "</head>"
    )


# ------------------------------------------------------------------ index
on_sel = []
for key, *_ in SECTIONS:
    on_sel += [
        f".home:has(.k-{key}:hover) .k-{key}",
        f".home:has(.k-{key}:focus-visible) .k-{key}",
    ]
ON = ",".join(on_sel)
ON_FALLBACK = ".map a:hover,.map a:focus-visible"


def sel(suffix):
    return ",".join(f"{s} {suffix}" for s in (ON_FALLBACK + "," + ON).split(","))


HOME_CSS = f"""
:root{{--ground:#EAF4F1;--ink:#1F2A1C;--muted:#4F5B58;--kicker:#44706A;--navy:#2F3B55;--navy2:#3A4868}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--ground);color:var(--ink);font-family:Merriweather,Georgia,"Times New Roman",serif}}
.home{{display:grid;grid-template-columns:minmax(300px,400px) 1fr;grid-template-rows:auto 1fr;grid-template-areas:"intro map" "nav map";
  column-gap:24px;min-height:100vh;min-height:100dvh;padding:56px 24px 24px 56px}}
.intro{{grid-area:intro;display:flex;flex-direction:column;gap:14px}}
.kicker{{margin:0;font:700 13px/1.4 system-ui,sans-serif;letter-spacing:2px;color:var(--kicker)}}
h1{{margin:0;font-weight:700;font-size:38px;line-height:1.2}}
h1 span{{display:block;margin-top:4px;font-size:18px;font-weight:400;color:var(--muted)}}
.who{{display:flex;align-items:center;gap:18px}}
.avatar{{flex:none;width:96px;height:96px;border-radius:50%;object-fit:cover;background:#D7E8E3;border:3px solid #fff;box-shadow:0 4px 14px rgba(47,59,85,.18)}}
.lead{{margin:0;font-size:15px;line-height:1.7;color:var(--muted)}}
.dash{{grid-area:nav;align-self:start;margin-top:18px;padding:18px 18px 14px;background:var(--navy);border-radius:14px;color:#fff}}
.dash-block+.dash-block{{margin-top:16px;padding-top:16px;border-top:1px solid rgba(201,210,227,.18)}}
.dash-h{{margin:0 0 10px;font:700 12px/1.4 system-ui,sans-serif;letter-spacing:2px;text-transform:uppercase;color:#C9D2E3}}
.tiles{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}}
.tile{{display:flex;flex-direction:column;justify-content:space-between;gap:6px;min-width:0;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.06);color:#fff;text-decoration:none;transition:background .2s,transform .2s}}
.tile .v{{font-weight:700;font-size:24px;line-height:1.1;font-variant-numeric:tabular-nums}}
.tile .l{{display:flex;align-items:flex-start;gap:6px;font:12px/1.3 system-ui,sans-serif;color:#C9D2E3}}
.tile .dot{{width:7px;height:7px;margin-top:4px;border-radius:50%;background:var(--c);flex:none}}
.tile.wide{{grid-column:span 2}}
a.tile:hover,a.tile:focus-visible{{background:rgba(255,255,255,.13);transform:translateY(-2px)}}
a.tile:focus-visible{{outline:2px solid #fff;outline-offset:2px}}
.dash-note{{margin:12px 0 0;font:11px/1.4 system-ui,sans-serif;color:#9AA6BF}}
.map-wrap{{grid-area:map;min-width:0;height:calc(100dvh - 80px);min-height:520px}}
.map{{display:block;width:100%;height:100%}}
.map a{{cursor:pointer;outline:none}}
.hl{{fill:#fff;fill-opacity:0;stroke:var(--c);stroke-width:3;stroke-opacity:0;stroke-linejoin:round;transition:fill-opacity .2s,stroke-opacity .2s,filter .2s}}
.tag{{transform-box:fill-box;transform-origin:50% 100%;transition:transform .25s cubic-bezier(.2,.8,.2,1)}}
.tag rect,.tag .tip{{transition:fill .2s}}
{sel(".hl")}{{fill-opacity:.2;stroke-opacity:1;filter:drop-shadow(0 0 10px var(--c))}}
{sel(".tag")}{{transform:translateY(-8px) scale(1.05)}}
{sel(".tag rect")},{sel(".tag .tip")}{{fill:var(--c)}}
{sel(".tag rect")}{{stroke:#fff}}
.hint{{grid-area:hint;display:none;margin:10px 0 0;font:13px/1.4 system-ui,sans-serif;color:var(--kicker);text-align:center}}
.foot{{position:fixed;right:20px;bottom:12px;font:12px system-ui,sans-serif;color:var(--kicker)}}
@media (max-width:1100px){{
  .home{{grid-template-columns:1fr;grid-template-rows:none;grid-template-areas:"intro" "map" "nav";padding:32px 24px 40px}}
  .intro{{max-width:640px}}
  .map-wrap{{height:auto;min-height:0;margin:8px -24px 0}}
  .map{{height:auto}}
  .dash{{display:grid;grid-template-columns:1fr 1fr;column-gap:28px}}
  .dash-block+.dash-block{{margin-top:0;padding-top:0;border-top:0}}
  .dash-note{{grid-column:1/-1}}
  .foot{{position:static;display:block;text-align:center;padding:0 0 24px}}
}}
@media (max-width:700px){{
  .home{{padding:24px 16px 32px;grid-template-areas:"intro" "map" "hint" "nav"}}
  h1{{font-size:30px}}
  .who{{gap:14px}}
  .avatar{{width:72px;height:72px}}
  .map-wrap{{margin:4px -16px 0;overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;scrollbar-width:none}}
  .map-wrap::-webkit-scrollbar{{display:none}}
  .map{{width:720px;max-width:none}}
  .hint{{display:block}}
  .dash{{display:block;margin-top:12px;padding:16px 14px 12px}}
  .dash-block+.dash-block{{margin-top:14px;padding-top:14px;border-top:1px solid rgba(201,210,227,.18)}}
  .tile{{padding:9px 10px}}
  .tile .v{{font-size:21px}}
}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
"""


def compact_css(css):
    css = re.sub(r"\s*\n\s*", "", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
    return css


import unicodedata
from datetime import date

PROJECTS_FILE = os.path.join(ROOT, "content", "projects.json")
PROJECTS = (json.load(open(PROJECTS_FILE, encoding="utf-8")) if os.path.exists(PROJECTS_FILE) else {}).get("projects", [])
TALKS_FILE = os.path.join(ROOT, "content", "talks.json")
TALKS = json.load(open(TALKS_FILE, encoding="utf-8")) if os.path.exists(TALKS_FILE) else {}
THIS_YEAR = int((PUBS.get("updated") or date.today().isoformat())[:4])
SCHOLAR = PUBS.get("scholar") or {}


def cite_count(w):
    """Google Scholar count when available (it is usually the highest), otherwise OpenAlex/Crossref."""
    return max(w.get("scholar_citations", 0), w["citations"]) if SCHOLAR else w["citations"]


def person_key(name):
    """'Merve Ataç', 'Ataç M' and 'MERVE ATAÇ' all map to 'atac|m'."""
    n = unicodedata.normalize("NFKD", name.replace("ı", "i").replace("İ", "I"))
    n = "".join(ch for ch in n if not unicodedata.combining(ch)).replace(".", " ")
    parts = n.split()
    if not parts:
        return ""
    if len(parts) > 1 and parts[-1].isupper() and len(parts[-1]) <= 3:  # Vancouver: "Uysal Sahin O"
        return f"{parts[-2].lower()}|{parts[-1][0].lower()}"
    return f"{parts[-1].lower()}|{parts[0][0].lower()}"


MY_KEYS = {person_key(a["name"]) for w in PUBS["works"] for a in w["authors"] if a["me"]} or {"kaplan|a"}


def project_active(p, year):
    start = p.get("start_year") or p.get("end_year")
    end = p.get("end_year") or THIS_YEAR
    return bool(start) and int(start) <= year <= int(end)


def metrics(year=None):
    works = [w for w in PUBS["works"] if year is None or w["year"] == year]
    projects = [p for p in PROJECTS if year is None or project_active(p, year)]
    people = {person_key(a["name"]) for w in works for a in w["authors"]}
    people |= {person_key(n) for p in projects for n in p.get("team", [])}
    people |= {person_key(a["name"]) for t in TALKS.get("presentations") or []
               if year is None or str(t.get("date", "")).startswith(str(year)) for a in t.get("authors", [])}
    people -= MY_KEYS | {""}
    if year is None:
        cites = SCHOLAR.get("citations") or sum(cite_count(w) for w in PUBS["works"])
    else:
        cites = (SCHOLAR.get("by_year") or {}).get(str(year)) if SCHOLAR else None
        if cites is None:
            cites = sum((w.get("citations_by_year") or {}).get(str(year), 0) for w in PUBS["works"])
    return {
        "papers": sum(w["section"] == "research" for w in works),
        "citations": cites,
        "projects": len(projects),
        "books": sum(w["section"] == "books" for w in works),
        "collab": len(people),
    }


COLORS = {k: c for k, _s, _t, _b, c, _p, _l in SECTIONS}


def tile(value, label, key=None, href=None, color=None):
    style = f' style="--c:{color or COLORS.get(key, "#C9D2E3")}"'
    inner = f'<span class="v">{value:,}</span><span class="l"><span class="dot"></span>{label}</span>'
    if href:
        return f'<a class="tile k-{key}" href="{href}"{style}>{inner}</a>'
    return f'<div class="tile wide"{style}>{inner}</div>'


def dash_block(title, m, cite_label):
    return (
        f'<div class="dash-block"><h2 class="dash-h">{title}</h2><div class="tiles">'
        + tile(m["papers"], "Research papers", "research", "research/")
        + tile(m["citations"], cite_label, "research", "research/")
        + tile(m["projects"], "Projects", "projects", "projects/")
        + tile(m["books"], "Books &amp; chapters", "books", "books/")
        + tile(m["collab"], "Collaborators", color="#E8DCC4")
        + "</div></div>"
    )


dashboard = (
    '<section class="dash" aria-label="Academic dashboard">'
    + dash_block("All time", metrics(), "Citations")
    + dash_block(str(THIS_YEAR), metrics(THIS_YEAR), f"Citations in {THIS_YEAR}")
    + f'<p class="dash-note">Collaborators: distinct co-authors and project partners. '
    + ("Citations: Google Scholar. " if SCHOLAR else "Citations: OpenAlex. ")
    + f'Updated {html.escape(PUBS.get("updated", ""))}.</p></section>'
)

person_ld = (
    '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Person",'
    f'"name":"Ali Kaplan","honorificSuffix":"PhD, RN","url":"{SITE}/","image":"{SITE}/assets/ali-kaplan.jpg",'
    '"knowsAbout":["Nursing management","Lean healthcare","Digital health"]}</script>'
)

INDEX_DESC = ("Academic portfolio of Ali Kaplan, PhD, RN: research papers, projects, teaching, books, "
              "talks and science communication in nursing management, lean healthcare and digital health.")
index_html = (
    head("Ali Kaplan, PhD, RN · Academic Portfolio", INDEX_DESC, "/",
         "<style>" + compact_css(HOME_CSS) + "</style>" + person_ld)
    + '<body><div class="home">'
    '<header class="intro"><p class="kicker">ACADEMIC PORTFOLIO</p>'
    f'<div class="who"><img class="avatar" src="assets/ali-kaplan.jpg?v={PHOTO_V}" width="96" height="96" '
    'alt="Portrait of Ali Kaplan" fetchpriority="high" decoding="async">'
    f'<h1>{NAME}<span>PhD, RN</span></h1></div>'
    '<p class="lead">Explore my work in nursing management, lean healthcare and digital health '
    'by walking through a hospital campus.</p></header>'
    f'<div class="map-wrap">{svg}</div>'
    f'{dashboard}'
    '<p class="hint" aria-hidden="true">Swipe to explore · tap a building</p>'
    "</div>"
    f'<footer class="foot">© {YEAR} Ali Kaplan</footer>'
    "<script>(function(){var w=document.querySelector('.map-wrap');"
    "if(w&&w.scrollWidth>w.clientWidth)w.scrollLeft=(w.scrollWidth-w.clientWidth)/2})()</script>"
    "</body></html>"
)

# --------------------------------------------------------------- subpages
SITE_CSS = """
:root{--ground:#EAF4F1;--ink:#1F2A1C;--muted:#4F5B58;--kicker:#44706A;--navy:#2F3B55;--card:#fff;--line:#CFE2DC}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);font-family:Merriweather,Georgia,"Times New Roman",serif;line-height:1.6}
a{color:inherit}
.top{position:sticky;top:0;z-index:10;background:var(--navy);color:#fff}
.bar{max-width:1040px;margin:0 auto;padding:12px 24px;display:flex;align-items:center;gap:16px}
.brand{text-decoration:none;font-weight:700;font-size:17px;display:flex;align-items:center;gap:10px}
.brand small{font:12px system-ui,sans-serif;color:#C9D2E3;font-weight:400}
.brand img{width:32px;height:32px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.85)}
.back{margin-left:auto;font:13px system-ui,sans-serif;color:#C9D2E3;text-decoration:none;padding:6px 12px;border:1px solid rgba(201,210,227,.3);border-radius:999px;white-space:nowrap}
.back:hover{color:#fff;border-color:#fff}
.tabs{max-width:1040px;margin:0 auto;padding:0 16px;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.tabs::-webkit-scrollbar{display:none}
.tabs a{flex:none;display:flex;align-items:center;gap:8px;padding:10px 12px 12px;color:#C9D2E3;text-decoration:none;font:600 14px system-ui,sans-serif;border-bottom:3px solid transparent;white-space:nowrap}
.tabs a:hover{color:#fff}
.tabs a[aria-current=page]{color:#fff;border-bottom-color:var(--c)}
.ic{width:18px;height:18px;flex:none;fill:none;stroke:var(--c);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.tabs a:hover .ic,.tabs a[aria-current=page] .ic{stroke:#fff}
main{max-width:1040px;margin:0 auto;padding:48px 24px 64px}
.kicker{margin:0 0 6px;font:700 13px/1.4 system-ui,sans-serif;letter-spacing:2px;text-transform:uppercase;color:var(--c)}
h1{margin:0 0 12px;font-size:clamp(28px,5vw,40px);line-height:1.2}
.lead{margin:0 0 36px;max-width:680px;color:var(--muted);font-size:16px}
.list{display:grid;gap:16px}
.item{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:12px;padding:20px 22px}
.item h2{margin:0 0 6px;font-size:18px;line-height:1.4}
.meta{margin:0;font:14px/1.5 system-ui,sans-serif;color:var(--muted)}
.item p{margin:8px 0 0;font-size:15px}
.item .links{margin-top:10px;font:600 14px system-ui,sans-serif}
.item .links a{color:var(--c);margin-right:14px}
.placeholder{opacity:.75;border-style:dashed}
.meta b{color:var(--ink)}
.venue{font-style:italic}
.alt-title{margin:-2px 0 8px;font-size:14px;font-style:italic;line-height:1.5;color:var(--muted)}
.badge{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:999px;background:var(--line);font:600 11px/1.6 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.5px;vertical-align:middle;color:var(--muted)}
.item h2 a{text-decoration:none}
.item h2 a:hover{text-decoration:underline;text-decoration-color:var(--c)}
.stats{display:flex;flex-wrap:wrap;align-items:center;gap:10px 20px;margin:0 0 24px;font:14px system-ui,sans-serif;color:var(--muted)}
.stats b{font-size:22px;color:var(--ink);margin-right:4px}
.stats input{margin-left:auto;flex:1 1 220px;max-width:320px;padding:9px 14px;border:1px solid var(--line);border-radius:999px;background:#fff;font:15px system-ui,sans-serif;color:var(--ink)}
.stats input:focus{outline:2px solid var(--c);outline-offset:1px}
.year{margin:28px 0 4px;font:700 13px system-ui,sans-serif;letter-spacing:2px;color:var(--kicker)}
.year:first-child{margin-top:0}
.updated{margin:28px 0 0;font:13px system-ui,sans-serif;color:var(--kicker)}
.empty{display:none;color:var(--muted)}
.kws{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:-6px 0 28px}
.kw{padding:5px 12px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink);font:600 13px/1.4 system-ui,sans-serif;cursor:pointer;transition:border-color .15s,background .15s}
.kw span{margin-left:4px;font-weight:400;color:var(--muted)}
.kw:hover{border-color:var(--kicker)}
.kw:focus-visible,.kw-clear:focus-visible,.more summary:focus-visible{outline:2px solid var(--kicker);outline-offset:2px}
.kw[aria-pressed=true]{background:var(--navy);border-color:var(--navy);color:#fff}
.kw[aria-pressed=true] span{color:#C9D2E3}
.kw-s{padding:2px 10px;border-color:transparent;background:var(--ground);font-weight:500;font-size:12px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.more summary{padding:5px 6px;font:600 13px system-ui,sans-serif;color:var(--kicker);cursor:pointer;list-style:none}
.more summary::-webkit-details-marker{display:none}
.more[open]{flex-basis:100%}
.kws-more{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}
.kw-clear{padding:5px 10px;border:0;background:none;color:var(--kicker);font:600 13px system-ui,sans-serif;text-decoration:underline;cursor:pointer}
.foot{max-width:1040px;margin:0 auto;padding:0 24px 40px;font:13px system-ui,sans-serif;color:var(--kicker)}
@media (max-width:600px){.bar{padding:10px 16px}.brand small{display:none}main{padding:32px 16px 48px}.item{padding:16px}
.stats input{margin-left:0;max-width:none;flex-basis:100%}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

SAMPLES = {
    "research": [("Title of your article", "Journal Name · 2026 · Authors",
                  "One-sentence summary of the study and its main finding.", ["DOI", "PDF"])],
    "projects": [("Project title", "Role: Principal investigator · Funder · 2025–2027",
                  "What the project does and what it has produced so far.", ["Project page"])],
    "teaching": [("Course name (code)", "Undergraduate · Spring semester · University",
                  "Short course description, topics and materials.", ["Syllabus"])],
    "books": [("Book title", "Publisher · 2026 · Author / Editor",
               "A short blurb about the book or chapter.", ["Publisher page"])],
    "talks": [("Talk or workshop title", "Event name · City · Date",
               "What the talk covered and who it was for.", ["Slides", "Video"])],
    "scicomm": [("Blog post, interview or media item", "Outlet · Date",
                 "A short description of the piece.", ["Read"])],
}


# Simple line icons (24x24, drawn with strokes) - inlined once per page as an SVG sprite: no extra requests.
ICONS = {
    "research": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "projects": '<path d="M9 3h6M10 3v6l-5.6 9.6A1.6 1.6 0 0 0 5.8 21h12.4a1.6 1.6 0 0 0 1.4-2.4L14 9V3"/><path d="M7.5 15h9"/>',
    "teaching": '<path d="M22 9 12 4 2 9l10 5 10-5z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5M22 9v6"/>',
    "books": '<path d="M2 5h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2zM22 5h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z"/>',
    "talks": '<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z"/><path d="M19 11a7 7 0 0 1-14 0M12 18v3M8 21h8"/>',
    "scicomm": '<path d="M3 11v2a1 1 0 0 0 1 1h3l6 4V6L7 10H4a1 1 0 0 0-1 1z"/><path d="M17 9a4 4 0 0 1 0 6M20 6a8 8 0 0 1 0 12"/>',
}
ICON_SPRITE = (
    '<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
    + "".join(f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in ICONS.items())
    + "</svg>"
)


def icon(key):
    return f'<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-{key}"/></svg>'


def tabs(active):
    return "".join(
        f'<a href="../{slug}/" style="--c:{color}"' + (' aria-current="page"' if key == active else "")
        + f'>{icon(key)}{html.escape(title)}</a>'
        for key, slug, title, building, color, polys, lead in SECTIONS
    )


def items(key):
    out = []
    for title, meta, desc, links in SAMPLES[key]:
        ls = "".join(f'<a href="#">{l}</a>' for l in links)
        out.append(
            "<!-- EXAMPLE ENTRY: copy this <article> block for each item, then delete the "
            '"placeholder" class. -->'
            f'<article class="item placeholder"><h2>{title}</h2><p class="meta">{meta}</p>'
            f'<p>{desc}</p><div class="links">{ls}</div></article>'
        )
    return "".join(out)


TYPE_LABEL = {"review": "Review", "letter": "Letter", "editorial": "Editorial", "preprint": "Preprint",
              "book-chapter": "Chapter", "book": "Book", "edited-book": "Edited book",
              "proceedings-article": "Proceedings", "conference-paper": "Conference",
              "conference-abstract": "Abstract", "book-review": "Book review", "dissertation": "Thesis",
              "report": "Report", "software": "Software"}
E = html.escape


def authors_html(authors, limit=12):
    names = [f"<b>{E(a['name'])}</b>" if a["me"] else E(a["name"]) for a in authors]
    if len(names) <= limit:
        return ", ".join(names)
    # Long author lists: first authors, then "…", then me (if hidden), then the last author.
    tail = [i for i in range(limit - 1, len(names)) if authors[i]["me"]]
    if len(names) - 1 not in tail:
        tail.append(len(names) - 1)
    return ", ".join(names[:limit - 1] + ["…"] + [names[i] for i in tail])


CONFIG_FILE = os.path.join(ROOT, "content", "publications-config.json")
KW_CFG = (json.load(open(CONFIG_FILE, encoding="utf-8")) if os.path.exists(CONFIG_FILE) else {}).get("keywords", {})
KW_HIDE = {k.lower() for k in KW_CFG.get("hide", [])}
KW_MERGE = {v.lower(): canon for canon, vs in (KW_CFG.get("merge") or {}).items() for v in vs}
KW_MAX = int(KW_CFG.get("max_per_paper", 5))


def all_keywords(w):
    """Every keyword for a paper (most relevant first), after hide/merge/add from the config."""
    extra = [k for key, ks in (KW_CFG.get("add") or {}).items()
             if w["title"].startswith(key) or (w["doi"] and w["doi"] == key.lower()) for k in ks]
    out, seen = [], set()
    for k in extra + list(w.get("keywords") or []):
        k = KW_MERGE.get(k.lower(), k)
        if k.lower() in KW_HIDE or k.lower() in seen:
            continue
        seen.add(k.lower())
        out.append(k)
    return out


def shown_keywords(w, shared):
    """Top keywords for the card, plus any keyword it shares with another paper (those make useful filters)."""
    out, own = [], 0
    for k in all_keywords(w):
        if k.lower() in shared:
            out.append(k)
        elif own < KW_MAX:
            out.append(k)
            own += 1
    return out


def kw_button(k, count=None, small=False):
    n = f" <span>{count}</span>" if count else ""
    cls = "kw kw-s" if small else "kw"
    return f'<button type="button" class="{cls}" data-kw="{E(k.lower())}" aria-pressed="false">{E(k)}{n}</button>'


def pub_item(w, shared=frozenset()):
    url = f"https://doi.org/{w['doi']}" if w["doi"] else (w["oa_url"] or "")
    title = E(w["title"])
    title = f'<a href="{E(url)}" rel="noopener">{title}</a>' if url else title
    badge = f'<span class="badge">{TYPE_LABEL[w["type"]]}</span>' if w["type"] in TYPE_LABEL else ""
    where = []
    if w["venue"]:
        where.append(f'<span class="venue">{E(w["venue"])}</span>')
    vol = E(str(w["volume"])) + (f"({E(str(w['issue']))})" if w["issue"] else "")
    if vol:
        where.append(vol + (f": {E(str(w['pages']))}" if w["pages"] else ""))
    if w["year"]:
        where.append(str(w["year"]))
    links = []
    if w["doi"]:
        links.append(f'<a href="https://doi.org/{E(w["doi"])}" rel="noopener">DOI</a>')
    if w["oa_url"] and w["oa_url"] != url:
        links.append(f'<a href="{E(w["oa_url"])}" rel="noopener">Open access</a>')
    n = cite_count(w)
    cites = ""
    if n:
        cites = (f'<a href="{E(w["scholar_link"])}" rel="noopener">Cited by {n}</a>' if w.get("scholar_link")
                 else f'<span class="meta">Cited by {n}</span>')
    kws = shown_keywords(w, shared)
    tags = f'<div class="tags">{"".join(kw_button(k, small=True) for k in kws)}</div>' if kws else ""
    data_kw = E("|".join(k.lower() for k in kws))
    return (
        f'<article class="item" data-kw="{data_kw}"><h2>{title}{badge}</h2>'
        + (f'<p class="alt-title" lang="tr">{E(w["alt_title"])}</p>' if w.get("alt_title") else "")
        + (f'<p class="meta">{authors_html(w["authors"])}{" (eds.)" if w.get("editors") else ""}</p>'
           if w["authors"] else "") +
        f'<p class="meta">{" · ".join(where)}</p>'
        f'<div class="links">{"".join(links)}{cites}</div>{tags}</article>'
    )


SEARCH_JS = (
    "<script>(function(){var q=document.getElementById('q');if(!q)return;"
    "var $=function(s){return[].slice.call(document.querySelectorAll(s))},items=$('.list .item'),years=$('.list .year'),"
    "e=document.querySelector('.empty'),clr=document.querySelector('.kw-clear'),active=null;"
    "items.forEach(function(i){i._t=i.textContent.toLowerCase();i._k=(i.getAttribute('data-kw')||'').split('|')});"
    "function apply(){var v=q.value.trim().toLowerCase(),n=0;"
    "items.forEach(function(i){var s=(!v||i._t.indexOf(v)>-1)&&(!active||i._k.indexOf(active)>-1);i.hidden=!s;if(s)n++});"
    "years.forEach(function(y){var el=y.nextElementSibling,any=false;"
    "while(el&&el.classList.contains('item')){if(!el.hidden)any=true;el=el.nextElementSibling}y.hidden=!any});"
    "e.style.display=n?'none':'block';"
    "$('.kw').forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-kw')===active)});"
    "if(clr)clr.hidden=!active;"
    "history.replaceState(null,'',active?'#kw='+encodeURIComponent(active):location.pathname+location.search)}"
    "q.addEventListener('input',apply);"
    "document.addEventListener('click',function(ev){var b=ev.target.closest('.kw,.kw-clear');if(!b)return;"
    "var k=b.classList.contains('kw-clear')?null:b.getAttribute('data-kw');active=active===k?null:k;apply();"
    "if(b.closest('.item')){var t=document.querySelector('.kws');if(t)t.scrollIntoView({behavior:'smooth',block:'center'})}});"
    "var m=location.hash.match(/^#kw=(.+)$/);if(m){active=decodeURIComponent(m[1]);apply()}"
    "})()</script>"
)


def pub_section(section):
    works = [w for w in PUBS["works"] if w.get("section") == section]
    if not works:
        return None, ""
    cites = sum(cite_count(w) for w in works)
    if SCHOLAR and section == "research":
        # Match the dashboard: Scholar's profile total, minus what belongs to the Books page.
        cites = SCHOLAR.get("citations", 0) - sum(cite_count(w) for w in PUBS["works"] if w["section"] != "research")
    noun = "publications" if section == "research" else "books & chapters"
    stats = (
        f'<div class="stats"><span><b>{len(works)}</b>{noun}</span>'
        + (f"<span><b>{cites}</b>citations</span>" if cites else "")
        + (f'<span><b>{SCHOLAR["h_index"]}</b>h-index</span>' if SCHOLAR.get("h_index") and section == "research" else "")
        + '<input id="q" type="search" placeholder="Search title, journal, co-author…" aria-label="Search publications">'
        "</div>"
    )
    counts = {}
    for w in works:
        for k in all_keywords(w):
            counts.setdefault(k.lower(), [k, 0])[1] += 1
    shared = {key for key, (_k, n) in counts.items() if n >= 2}
    shown = {}
    for w in works:
        for k in shown_keywords(w, shared):
            shown.setdefault(k.lower(), k)
    # Main bar: keywords shared by 2+ papers, then each paper's single most relevant keyword.
    main = set(shared)
    for w in works:
        ks = all_keywords(w)
        if ks:
            main.add(ks[0].lower())
    top = sorted((counts[key] for key in main), key=lambda kn: (-kn[1], kn[0].lower()))
    rest = sorted((v for key, v in shown.items() if key not in main), key=str.lower)
    kwbar = ""
    if top or rest:
        kwbar = (
            '<div class="kws" role="group" aria-label="Filter by keyword">'
            + "".join(kw_button(k, n) for k, n in top)
            + (f'<details class="more"><summary>+ {len(rest)} more topics</summary><div class="kws-more">'
               + "".join(kw_button(k) for k in rest) + "</div></details>" if rest else "")
            + '<button type="button" class="kw-clear" hidden>× Clear filter</button></div>'
        )
    body, year = [], None
    for w in works:
        if w["year"] != year:
            year = w["year"]
            body.append(f'<h3 class="year">{year or "Undated"}</h3>')
        body.append(pub_item(w, shared))
    body.append('<p class="empty">No publications match your search.</p>')
    used = {w["source"] for w in works}
    names = [n for k, n in (("openalex", "OpenAlex"), ("orcid", "ORCID"), ("crossref", "Crossref")) if k in used]
    src = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
    cite_src = ["Google Scholar"] if SCHOLAR else [n for n in names if n != "ORCID"]
    foot = (f'<p class="updated">Updated automatically from {src} on {E(PUBS.get("updated", ""))}.'
            + (f' Citation counts are from {" and ".join(cite_src)}.' if cites and cite_src else "") + "</p>")
    return stats + kwbar + f'<section class="list">{"".join(body)}</section>' + foot, SEARCH_JS


TEACHING_FILE = os.path.join(ROOT, "content", "teaching.json")
TEACHING = json.load(open(TEACHING_FILE, encoding="utf-8")) if os.path.exists(TEACHING_FILE) else {}


def teaching_section():
    courses, training = TEACHING.get("courses") or [], TEACHING.get("training") or []
    if not courses and not training:
        return None

    def card(title, title_tr, meta):
        return (f'<article class="item"><h2>{E(title)}</h2>'
                + (f'<p class="alt-title" lang="tr">{E(title_tr)}</p>' if title_tr else "")
                + f'<p class="meta">{" · ".join(E(m) for m in meta if m)}</p></article>')

    out = []
    for level, heading in (("graduate", "Graduate courses"), ("undergraduate", "Undergraduate courses")):
        group = [c for c in courses if c.get("level") == level]
        if group:
            out.append(f'<h3 class="year">{heading}</h3>')
            out += [card(c["title"], c.get("title_tr"),
                         [c.get("code"), c.get("type"), f'Taught in {c["language"]}' if c.get("language") else "",
                          ", ".join(c.get("terms") or [])]) for c in group]
    if training:
        out.append('<h3 class="year">Training programmes</h3>')
        out += [card(t["title"], t.get("title_tr"), [t.get("organiser"), t.get("years")]) for t in training]
    stats = (f'<div class="stats"><span><b>{len(courses)}</b>courses</span>'
             + (f'<span><b>{len(training)}</b>training programme{"s" if len(training) != 1 else ""}</span>' if training else "")
             + "</div>")
    return stats + f'<section class="list">{"".join(out)}</section>'


def talks_section():
    invited, pres = TALKS.get("invited") or [], TALKS.get("presentations") or []
    if not invited and not pres:
        return None

    def card(t, meta, extra=""):
        url = t.get("url")
        title = E(t["title"])
        title = f'<a href="{E(url)}" rel="noopener">{title}</a>' if url else title
        badge = f'<span class="badge">{E(t["type"])}</span>' if t.get("type") else ""
        return (f'<article class="item"><h2>{title}{badge}</h2>'
                + (f'<p class="alt-title" lang="tr">{E(t["title_tr"])}</p>' if t.get("title_tr") else "")
                + extra + f'<p class="meta">{" · ".join(E(m) for m in meta if m)}</p></article>')

    out = []
    if invited:
        out.append('<h3 class="year">Invited talks</h3>')
        out += [card(t, [t.get("venue"), t.get("date_text")])
                for t in sorted(invited, key=lambda t: t.get("date", ""), reverse=True)]
    if pres:
        out.append('<h3 class="year">Conference presentations</h3>')
        for t in sorted(pres, key=lambda t: t.get("date", ""), reverse=True):
            authors = f'<p class="meta">{authors_html(t["authors"])}</p>' if t.get("authors") else ""
            out.append(card(t, [t.get("event"), t.get("place"), t.get("date_text"), t.get("format")], authors))
    stats = (f'<div class="stats">'
             + (f'<span><b>{len(invited)}</b>invited talk{"s" if len(invited) != 1 else ""}</span>' if invited else "")
             + (f'<span><b>{len(pres)}</b>conference presentation{"s" if len(pres) != 1 else ""}</span>' if pres else "")
             + "</div>")
    return stats + f'<section class="list">{"".join(out)}</section>'


def project_section():
    if not PROJECTS:
        return None
    ordered = sorted(PROJECTS, key=lambda p: (p.get("end_year") or 9999, p.get("start_year") or 0), reverse=True)
    out = []
    for p in ordered:
        years = f'{p.get("start_year", "")}–{p.get("end_year") or "ongoing"}'
        meta = " · ".join(E(str(x)) for x in (p.get("role"), p.get("funder"), years) if x)
        team = ", ".join(E(n) for n in p.get("team", []))
        link = f'<div class="links"><a href="{E(p["url"])}" rel="noopener">Project page</a></div>' if p.get("url") else ""
        out.append(
            f'<article class="item"><h2>{E(p["title"])}</h2>'
            + (f'<p class="alt-title" lang="tr">{E(p["title_tr"])}</p>' if p.get("title_tr") else "")
            + f'<p class="meta">{meta}</p>'
            + (f'<p>{E(p["description"])}</p>' if p.get("description") else "")
            + (f'<p class="meta">Team: {team}</p>' if team else "") + link + "</article>"
        )
    return f'<section class="list">{"".join(out)}</section>'


CSS_V = hashlib.sha1(compact_css(SITE_CSS).encode()).hexdigest()[:8]
pages = {}
for key, slug, title, building, color, polys, lead in SECTIONS:
    if key in ("research", "books"):
        content, page_js = pub_section(key)
    elif key == "talks":
        content, page_js = talks_section(), ""
    elif key == "teaching":
        content, page_js = teaching_section(), ""
    elif key == "projects":
        content, page_js = project_section(), ""
    else:
        content, page_js = None, ""
    content = content or f'<section class="list">{items(key)}</section>'
    pages[f"{slug}/index.html"] = (
        head(f"{title} · Ali Kaplan, PhD, RN", lead, f"/{slug}/",
             '<link rel="stylesheet" href="../assets/site.css?v=' + CSS_V + '">')
        + f'<body style="--c:{color}">{ICON_SPRITE}'
        '<header class="top"><div class="bar">'
        f'<a class="brand" href="../"><img src="../assets/ali-kaplan.jpg?v={PHOTO_V}" width="32" height="32" alt="" decoding="async">'
        f'{NAME} <small>PhD, RN</small></a>'
        '<a class="back" href="../">← Campus map</a></div>'
        f'<nav class="tabs" aria-label="Sections">{tabs(key)}</nav></header>'
        f'<main><p class="kicker">{html.escape(building)}</p><h1>{html.escape(title)}</h1>'
        f'<p class="lead">{html.escape(lead)}</p>'
        f'{content}</main>'
        f'<footer class="foot">© {YEAR} Ali Kaplan · <a href="../">Back to the campus</a></footer>'
        "<script>(function(){var t=document.querySelector('.tabs'),a=t&&t.querySelector('[aria-current]');"
        "if(a)t.scrollLeft=a.offsetLeft-(t.clientWidth-a.offsetWidth)/2})()</script>"
        + page_js + "</body></html>"
    )

# ------------------------------------------------------------ misc files
ROBOTS = f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n"
SITEMAP = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"  <url><loc>{SITE}/{u}</loc></url>\n" for u in [""] + [s[1] + "/" for s in SECTIONS])
           + "</urlset>\n")
HTACCESS = """# Apache: compression and browser caching for dralikaplan.com
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css application/javascript image/svg+xml application/xml text/plain
</IfModule>
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType text/html "access plus 0 seconds"
  ExpiresByType text/css "access plus 1 month"
  ExpiresByType image/svg+xml "access plus 1 month"
  ExpiresByType image/jpeg "access plus 1 year"
</IfModule>
<IfModule mod_headers.c>
  # Pages are always re-checked, so visitors never see an outdated version.
  <FilesMatch "\\.html$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  # CSS and images carry ?v=<hash> in their URL, so they can be cached for long.
  <FilesMatch "\\.(css|jpg|svg)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
</IfModule>
Options -Indexes
"""

files = {"index.html": index_html, "assets/site.css": compact_css(SITE_CSS),
         "robots.txt": ROBOTS, "sitemap.xml": SITEMAP, ".htaccess": HTACCESS,
         "CNAME": DOMAIN + "\n",  # custom domain for GitHub Pages
         ".nojekyll": "", **pages}
if os.path.isdir(STATIC):
    shutil.copytree(STATIC, OUT, dirs_exist_ok=True)
for path, content in files.items():
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{len(content.encode()):>7}  {path}")
