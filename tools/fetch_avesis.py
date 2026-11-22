"""Read projects, courses and training programmes from the public Avesis profile.

Writes content/projects.json and content/teaching.json. English titles/descriptions come from
content/translations.json (keyed by the Turkish text on Avesis); anything not translated yet is
shown in Turkish and listed at the end of the run.

Usage: python3 tools/fetch_avesis.py
If Avesis cannot be reached or its layout changes, the existing files are kept unchanged.
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
CONFIG = json.load(open(os.path.join(CONTENT, "publications-config.json"), encoding="utf-8"))
AVESIS = (CONFIG.get("avesis_profile") or "https://avesis.comu.edu.tr/alikaplan").rstrip("/")
BASE = re.match(r"https?://[^/]+", AVESIS).group(0)
USER = AVESIS.rsplit("/", 1)[-1]
TR = json.load(open(os.path.join(CONTENT, "translations.json"), encoding="utf-8"))
UA = "dralikaplan.com site builder (python-urllib)"
missing = []


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return html.unescape(r.read().decode("utf-8", "replace"))
        except Exception:
            if i == 2:
                raise
            time.sleep(3 * (i + 1))


def text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def norm(s):
    return re.sub(r"\s+,", ",", re.sub(r"\s+", " ", s or "")).strip()


def en_title(tr):
    if tr in TR.get("titles", {}):
        return TR["titles"][tr]
    missing.append(f'titles: "{tr}"')
    return ""


def en_funder(tr):
    tr = norm(tr)
    if not tr:
        return ""
    if tr in TR.get("funders", {}):
        return TR["funders"][tr]
    missing.append(f'funders: "{tr}"')
    return tr


def en_word(w):
    return TR.get("words", {}).get(w, w)


def is_me(name):
    parts = name.replace(".", " ").split()
    fam = CONFIG.get("my_family_name", "").lower()
    ini = CONFIG.get("my_given_initial", "").lower()
    return bool(parts) and parts[0].lower() == fam and parts[-1][:1].lower() == ini


def section(page, heading):
    """HTML of the accordion block whose header is `heading`."""
    i = page.find(f"<span>{heading}</span>")
    if i < 0:
        return ""
    j = page.find('<div class="ac-item', i)
    return page[i: j if j > 0 else len(page)]


def team_of(block):
    """(team names without me, my role) from the 'authorsRichText' links."""
    team, role = [], "Researcher"
    for m in re.finditer(r"<a class='authorsRichText'([^>]*)>([^<]*)</a>\s*(\(([^)]*)\))?", block):
        attrs, short, _, marker = m.groups()
        full = re.search(r"title ='([^']*)'", attrs)
        name = (full.group(1) if full else short).strip()
        if is_me(short.strip()):
            if marker and "Yürütücü" in marker:
                role = "Principal investigator"
            continue
        team.append(name)
    return team, role


def projects(page):
    out = []
    for li in re.findall(r"<li>\s*<h3 class=\"project-item title\">(.*?)</li>", page, re.S):
        years = re.search(r'shaded-label">\s*(\d{4})\s*-\s*(\d{4}|Devam Ediyor)?', li)
        link = re.search(r'href="(/proje/[^"]+)"', li)
        title_tr = text((re.search(r"<strong>(.*?)</strong>", li, re.S) or [None, ""])[1])
        funder_tr = text((re.search(r'<div class="description">\s*<p[^>]*>(.*?)</p>', li, re.S) or [None, ""])[1])
        team, role = team_of(li)
        title = en_title(title_tr)
        out.append({
            "title": title or title_tr,
            "title_tr": title_tr if title else "",
            "role": role,
            "funder": en_funder(funder_tr),
            "start_year": int(years.group(1)) if years else None,
            "end_year": int(years.group(2)) if years and years.group(2) and years.group(2).isdigit() else None,
            "team": team,
            "description": TR.get("descriptions", {}).get(title_tr, ""),
            "url": BASE + link.group(1) if link else "",
        })
    return out


def course_details(lesson_id):
    q = f"?id={USER}&lessonId={lesson_id}"
    info = text(get(f"{BASE}/resume/lessoncontent{q}"))
    terms = text(get(f"{BASE}/resume/lessonsemesters{q}"))

    def field(label):
        m = re.search(label + r":?\s*(.+?)(?=\s+(?:Kurum Adı|Fakülte|Bölüm|Dersin Türü|Öğretim Türü|Dersin Dili)\b|\s*$)", info)
        return m.group(1).strip() if m else ""
    sems = [f"{a}–{b} {en_word(s)}" for a, b, s in re.findall(r"(\d{4})\s*-\s*(\d{4}),\s*(\w+)", terms)]
    return field("Dersin Kodu"), en_word(field("Dersin Türü")), en_word(field("Dersin Dili")), sems


LEVELS = {"Yüksek Lisans": "graduate", "Lisans": "undergraduate", "Doktora": "doctoral", "Ön Lisans": "associate"}


def courses(page):
    block = section(page, "Verdiği Dersler")
    out = []
    for li in re.findall(r"<li>(.*?)</li>", block, re.S):
        level = text((re.search(r"<span[^>]*>(.*?)</span>", li, re.S) or [None, ""])[1])
        for name, lesson_id in re.findall(r'<h3 class="title"[^>]*>\s*([^<]+?)\s*<a[^>]*lessonId=([\w-]+)', li):
            code, ctype, lang, terms = course_details(lesson_id)
            title = en_title(name.strip())
            out.append({"level": LEVELS.get(level, "other"), "title": title or name.strip(),
                        "title_tr": name.strip() if title else "", "code": code, "type": ctype,
                        "language": lang, "terms": terms})
            time.sleep(0.3)
    return out


def training(page):
    block = section(page, "Verdiği Kurs ve Eğitimler")
    out = []
    for li in re.findall(r"<li>(.*?)</li>", block, re.S):
        years = re.search(r'shaded-label">\s*(\d{4})\s*-\s*(\d{4})', li)
        h3 = re.search(r'<h3 class="title">(.*?)</h3>', li, re.S)
        name = text(re.sub(r'<span class="shaded-label">.*?</span>', "", h3.group(1), flags=re.S)) if h3 else ""
        org = text((re.search(r'<div class="description">\s*<p>(.*?)</p>', li, re.S) or [None, ""])[1])
        if not name:
            continue
        title = en_title(name)
        yrs = ""
        if years:
            a, b = years.groups()
            yrs = a if a == b else f"{a}–{b}"
        out.append({"title": title or name, "title_tr": name if title else "",
                    "organiser": en_funder(org), "years": yrs})
    return out


MONTHS = {"Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6, "Temmuz": 7,
          "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12}


def tr_date(s):
    """'17 Haziran 2021' / 'Eylül 2026' / '2021' -> ('2021-06-17', '17 June 2021')."""
    m = re.search(r"(?:(\d{1,2})\s+)?(?:(" + "|".join(MONTHS) + r")\s+)?(\d{4})", s or "")
    if not m:
        return "", ""
    day, month, year = m.groups()
    iso = year + (f"-{MONTHS[month]:02d}" if month else "") + (f"-{int(day):02d}" if month and day else "")
    text = " ".join(p for p in (day, en_word(month) if month else "", year) if p)
    return iso, text


def fix_caps(name):
    """'ORHAN ÇAKIR' -> 'Orhan Çakır', 'ATAÇ M.' -> 'Ataç M.' (Turkish dotted/dotless i aware)."""
    def word(w):
        if len(w) < 3 or not w.isupper():
            return w
        return w[0] + w[1:].replace("I", "ı").replace("İ", "i").lower()
    return " ".join(word(w) for w in name.split())


def en_event(s):
    s = norm(s)
    return TR.get("events", {}).get(s, s)


def invited_talks(page):
    block = section(page, "Davetli Konuşmalar")
    out = []
    for li in re.findall(r"<li>(.*?)</li>", block, re.S):
        h3 = re.search(r'<h3 class="title">(.*?)</h3>', li, re.S)
        if not h3:
            continue
        when = text((re.search(r'shaded-label">(.*?)</span>', h3.group(1), re.S) or [None, ""])[1])
        name = text(re.sub(r'<span class="shaded-label">.*?</span>', "", h3.group(1), flags=re.S))
        ps = [text(p) for p in re.findall(r"<p>(.*?)</p>", li, re.S)]
        kind = en_word(ps[0]) if ps else ""
        venue = ", ".join(en_event(x.strip()) for x in ps[1].split(",")) if len(ps) > 1 else ""
        iso, when_en = tr_date(when)
        title = en_title(name)
        out.append({"title": title or name, "title_tr": name if title else "", "type": kind,
                    "venue": venue, "date": iso, "date_text": when_en})
    return out


def presentations(page):
    block = section(page, "Hakemli Bilimsel Toplantılarda Yayımlanmış Bildiriler")
    out = []
    for item in re.split(r'<div class="pub-item', block)[1:]:
        link = re.search(r'href="(/yayin/[^"]+)"', item)
        name = text((re.search(r"<strong>(.*?)</strong>", item, re.S) or [None, ""])[1])
        cits = re.findall(r'<div class="citation"[^>]*>(.*?)</div>', item, re.S)
        authors = []
        if cits:
            for attrs, short in re.findall(r"<a class='authorsRichText'([^>]*)>([^<]*)</a>", cits[0]):
                full = re.search(r"title ='([^']+)'", attrs)
                short = short.strip()
                if is_me(short):
                    authors.append({"name": "Kaplan A.", "me": True})
                else:
                    authors.append({"name": fix_caps(full.group(1) if full else short), "me": False})
        info = text(re.sub(r"<span.*?</span>", "", cits[1], flags=re.S)) if len(cits) > 1 else ""
        ext = re.search(r'<a href="(https?://[^"]+)"[^>]*class="link-with-icon"', cits[1] if len(cits) > 1 else "")
        fmt = re.search(r"\(([^)]+)\)\s*$", info)
        parts = [p.strip() for p in re.sub(r",?\s*\([^)]+\)\s*$", "", info).split(",") if p.strip()]
        iso, when_en = tr_date(parts[-1] if parts else "")
        if when_en:
            parts = parts[:-1]
        event = en_event(parts[0]) if parts else ""
        place = ", ".join(parts[1:])
        title = en_title(name)
        out.append({"title": title or name, "title_tr": name if title else "", "authors": authors,
                    "event": event, "place": place, "date": iso, "date_text": when_en,
                    "format": en_word(fmt.group(1)) if fmt else "",
                    "url": ext.group(1) if ext else (BASE + link.group(1) if link else "")})
    return out


def save(name, data):
    path = os.path.join(CONTENT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    print(f"Avesis: {AVESIS}")
    try:
        proj_page, exp_page = get(f"{AVESIS}/projeler"), get(f"{AVESIS}/deneyim")
        p, c, t = projects(proj_page), courses(exp_page), training(exp_page)
        talks, pres = invited_talks(get(f"{AVESIS}/basarilar")), presentations(get(f"{AVESIS}/yayinlar"))
    except Exception as e:  # network or layout problem: keep what we have
        print(f"::warning::Avesis could not be read ({e}); keeping the existing projects and teaching files.")
        return
    if not p and not c and not t:
        print("::warning::Nothing found on Avesis (layout changed?); keeping the existing files.")
        return
    save("projects.json", {"source": f"{AVESIS}/projeler", "projects": p})
    save("teaching.json", {"source": f"{AVESIS}/deneyim", "institution": CONFIG.get("institution", ""),
                           "courses": c, "training": t})
    save("talks.json", {"source": f"{AVESIS}/basarilar", "invited": talks, "presentations": pres})
    print(f"  {len(p)} projects, {len(c)} courses, {len(t)} training programmes, "
          f"{len(talks)} invited talks, {len(pres)} conference presentations")
    for m in dict.fromkeys(missing):
        print(f"::notice::Needs an English entry in content/translations.json -> {m}")


if __name__ == "__main__":
    main()
