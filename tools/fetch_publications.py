"""Fetch publications from free, key-less APIs and save them to content/publications.json.

Sources
  * OpenAlex (https://openalex.org)  - every work linked to the ORCID in the config.
  * ORCID    (https://orcid.org)     - the public ORCID record, to catch works OpenAlex misses
                                       (DOIs are completed from Crossref; works without a DOI
                                       are taken from the ORCID record itself).
  * Crossref (https://crossref.org)  - any extra DOIs listed in the config.

Usage:  python3 tools/fetch_publications.py
Then:   python3 tools/build_site.py
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "content", "publications-config.json")
OUTPUT = os.path.join(ROOT, "content", "publications.json")
UA = "dralikaplan.com publication fetcher (python-urllib)"

# OpenAlex / Crossref types that belong on the Books page; everything else goes to Research Papers.
BOOK_TYPES = {"book", "book-chapter", "monograph", "edited-book", "reference-book"}
SKIP_TYPES = {"paratext", "dataset", "peer-review", "erratum", "retraction", "supplementary-materials"}


KEY_HINT = ("OpenAlex limits key-less use; try again later, or add a free key from "
            "https://openalex.org/settings/api as \"openalex_api_key\" in content/publications-config.json.")


class ApiLimit(Exception):
    pass


def get_json(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code in (401, 403) or i == tries - 1:
                raise ApiLimit(f"HTTP {e.code} from {url.split('?')[0]}: {body}")
        except urllib.error.URLError:
            if i == tries - 1:
                raise
        time.sleep(2 * (i + 1))


def clean(text):
    """Strip HTML/JATS tags that some titles carry, collapse whitespace."""
    text = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def fix_caps(name):
    """'Damla GÖKALP' -> 'Damla Gökalp', with Turkish dotted/dotless i handled."""
    def word(w):
        if len(w) < 3 or not w.isupper():
            return w
        low = w[1:].replace("I", "ı").replace("İ", "i").lower()
        return w[0] + low
    return " ".join(word(w) for w in (name or "").split())


def pages(first, last):
    first, last = (first or "").strip(), (last or "").strip()
    return first if not last or last == first else f"{first}-{last}"


# Preprint servers whose records often carry no venue name.
DOI_PREFIX_VENUE = {"10.17605/osf.io": "OSF Preprints", "10.21203/rs.": "Research Square",
                    "10.31234/osf.io": "PsyArXiv", "10.1101/": "bioRxiv / medRxiv", "10.20944/preprints": "Preprints.org"}


def venue_from_doi(doi):
    return next((v for p, v in DOI_PREFIX_VENUE.items() if doi.startswith(p)), "")


def norm_doi(doi):
    doi = (doi or "").strip().lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi)


def norm_orcid(orcid):
    m = re.search(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", orcid or "", re.I)
    return m.group(0).upper() if m else ""


def is_me(name, orcid, cfg):
    if orcid and norm_orcid(orcid) == cfg["_orcid"]:
        return True
    parts = name.replace(".", " ").split()
    fam = cfg.get("my_family_name", "").lower()
    ini = cfg.get("my_given_initial", "").lower()
    if not (parts and fam):
        return False
    if len(parts) > 1 and parts[-1].isupper() and len(parts[-1]) <= 3:  # Vancouver style: "Kaplan A"
        return parts[0].lower() == fam and parts[-1][:1].lower() == ini
    return parts[-1].lower() == fam and parts[0][:1].lower() == ini


# ------------------------------------------------------------------ OpenAlex
def from_openalex(cfg):
    orcid = cfg["_orcid"]
    if not orcid:
        return []
    works, page, per_page = [], 1, 200
    while True:
        params = {
            "filter": f"author.orcid:https://orcid.org/{orcid}",
            "per-page": per_page, "page": page, "sort": "publication_date:desc",
            "select": "id,doi,display_name,publication_year,publication_date,type,primary_location,"
                      "authorships,cited_by_count,counts_by_year,open_access,biblio,is_retracted,keywords",
        }
        if cfg.get("openalex_api_key"):
            params["api_key"] = cfg["openalex_api_key"]
        try:
            data = get_json(f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}")
        except ApiLimit as e:
            if page == 1:
                sys.exit(f"{e}\n{KEY_HINT}")
            print(f"  ! Stopped after {len(works)} works (newest first): {e}\n  {KEY_HINT}", file=sys.stderr)
            break
        if not data:
            break
        for w in data["results"]:
            if w.get("is_retracted") or w.get("type") in SKIP_TYPES:
                continue
            src = ((w.get("primary_location") or {}).get("source") or {})
            authors = []
            for a in w.get("authorships") or []:
                au = a.get("author") or {}
                name = fix_caps(au.get("display_name") or "")
                authors.append({"name": name, "me": is_me(name, au.get("orcid"), cfg)})
            b = w.get("biblio") or {}
            works.append({
                "title": clean(w.get("display_name")),
                "authors": authors,
                "venue": clean(src.get("display_name")),
                "year": w.get("publication_year"),
                "date": w.get("publication_date") or "",
                "type": w.get("type") or "article",
                "doi": norm_doi(w.get("doi")),
                "volume": b.get("volume") or "", "issue": b.get("issue") or "",
                "pages": pages(b.get("first_page"), b.get("last_page")),
                "oa_url": (w.get("open_access") or {}).get("oa_url") or "",
                "citations": w.get("cited_by_count") or 0,
                "citations_by_year": {str(c["year"]): c["cited_by_count"] for c in w.get("counts_by_year") or []},
                "keywords": [k["display_name"] for k in sorted(w.get("keywords") or [], key=lambda k: -k.get("score", 0))],
                "source": "openalex", "openalex_id": w.get("id"),
            })
        total = (data.get("meta") or {}).get("count") or 0
        if len(data["results"]) < per_page or page * per_page >= total:
            break
        page += 1
        time.sleep(0.2)
    return works


# ------------------------------------------------------------------ Crossref
def from_crossref(doi, cfg):
    try:
        data = get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    except ApiLimit as e:
        print(f"  ! Crossref request failed for {doi}: {e}", file=sys.stderr)
        return None
    if not data:
        print(f"  ! DOI not found on Crossref: {doi}", file=sys.stderr)
        return None
    m = data["message"]
    authors = []
    for a in m.get("author") or []:
        name = fix_caps(" ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name", ""))
        authors.append({"name": name, "me": is_me(name, a.get("ORCID"), cfg)})
    typ = m.get("type", "journal-article")
    editors = []
    for a in m.get("editor") or []:
        name = fix_caps(" ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name", ""))
        editors.append({"name": name, "me": is_me(name, a.get("ORCID"), cfg)})
    if editors and (typ in ("edited-book", "book", "monograph") or not authors):
        authors = editors  # for an edited book the listed "authors" are the chapter authors
    parts = (m.get("issued") or m.get("published") or {}).get("date-parts") or [[None]]
    ymd = [p for p in parts[0] if p]
    return {
        "title": clean((m.get("title") or [""])[0]),
        "authors": authors,
        "venue": clean((m.get("container-title") or [""])[0]) or clean(m.get("publisher")),
        "year": ymd[0] if ymd else None,
        "date": "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(ymd)),
        "type": {"journal-article": "article", "proceedings-article": "article"}.get(typ, typ),
        "doi": norm_doi(m.get("DOI")),
        "volume": m.get("volume", ""), "issue": m.get("issue", ""), "pages": m.get("page", ""),
        "oa_url": "",
        "citations": m.get("is-referenced-by-count") or 0,
        "keywords": [clean(k) for k in m.get("subject") or []],
        "editors": bool(editors) and authors is editors,
        "source": "crossref",
    }


# ------------------------------------------------------------------ ORCID
ORCID_TYPES = {"journal-article": "article", "conference-paper": "conference-paper", "book-chapter": "book-chapter",
               "book": "book", "edited-book": "edited-book", "preprint": "preprint",
               "dissertation-thesis": "dissertation", "report": "report"}


def orcid_get(orcid, path):
    try:
        return get_json(f"https://pub.orcid.org/v3.0/{orcid}/{path}")
    except ApiLimit as e:
        print(f"  ! ORCID request failed: {e}", file=sys.stderr)
        return None


def parse_citation(text):
    """Pull authors and volume/issue/pages out of a Vancouver-style citation, e.g.
    'Ataç M, Kaplan A. Title. J Educ Res Nurs. 2021;18(Supp. 1): 54-59.'"""
    text = re.sub(r"\s+", " ", text or "").strip()
    out = {"authors": [], "volume": "", "issue": "", "pages": ""}
    m = re.match(r"^((?:[^.,;]+? [A-Z]{1,3}(?:, |\.))+)", text)
    if m:
        out["authors"] = [a.strip(" .") for a in m.group(1).split(",") if a.strip(" .")]
    m = re.search(r"\b(?:19|20)\d{2}\s*;\s*([^():;]+?)\s*(?:\(([^)]+)\))?\s*:\s*([\w\-–]+)", text)
    if m:
        out["volume"], out["issue"], out["pages"] = m.group(1).strip(), (m.group(2) or "").strip(), m.group(3)
    return out


def from_orcid(cfg):
    """Returns ({doi: ORCID title/venue}, works_without_doi) from the public ORCID record."""
    orcid = cfg["_orcid"]
    data = orcid_get(orcid, "works")
    if not data:
        return {}, []
    dois, works = {}, []
    for group in data.get("group") or []:
        s = group["work-summary"][0]
        ids = ((s.get("external-ids") or {}).get("external-id")) or []
        doi = next((norm_doi(e["external-id-value"]) for e in ids if e["external-id-type"] == "doi"), "")
        if doi:
            dois[doi] = {"title": clean(((s.get("title") or {}).get("title") or {}).get("value")),
                         "venue": clean((s.get("journal-title") or {}).get("value"))}
            continue
        w = orcid_get(orcid, f"work/{s['put-code']}") or s
        cit = parse_citation((w.get("citation") or {}).get("citation-value"))
        names = [(c.get("credit-name") or {}).get("value") for c in (w.get("contributors") or {}).get("contributor") or []]
        names = [fix_caps(n) for n in names if n] or cit["authors"]
        pd = w.get("publication-date") or {}
        ymd = [(pd.get(k) or {}).get("value") for k in ("year", "month", "day")]
        works.append({
            "title": clean(((w.get("title") or {}).get("title") or {}).get("value")),
            "authors": [{"name": n, "me": is_me(n, None, cfg)} for n in names],
            "venue": clean((w.get("journal-title") or {}).get("value")),
            "year": int(ymd[0]) if ymd[0] else None,
            "date": "-".join(p for p in ymd if p),
            "type": ORCID_TYPES.get(w.get("type"), w.get("type") or "other"),
            "doi": "",
            "volume": cit["volume"], "issue": cit["issue"], "pages": cit["pages"],
            "oa_url": (w.get("url") or {}).get("value") or "",
            "citations": 0,
            "keywords": [],
            "source": "orcid",
        })
    return dois, works


# ------------------------------------------------------------------ Google Scholar (via SerpApi)
SECRETS = os.path.join(ROOT, "content", "secrets.json")


def serpapi_key():
    if os.environ.get("SERPAPI_KEY"):
        return os.environ["SERPAPI_KEY"].strip()
    if os.path.exists(SECRETS):
        return (json.load(open(SECRETS, encoding="utf-8")).get("serpapi_key") or "").strip()
    return ""


def scholar_id(value):
    m = re.search(r"user=([\w-]{12})", value or "")
    return m.group(1) if m else (value or "").strip()


def fold_tokens(text):
    import unicodedata
    t = unicodedata.normalize("NFKD", (text or "").replace("ı", "i").replace("İ", "I").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return set(re.findall(r"[a-z0-9]{3,}", t))


def overlap(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def match_scholar(article, works):
    """Find the work a Scholar article refers to (titles may differ in language, so venue/volume count too)."""
    st = fold_tokens(article.get("title"))
    pub = article.get("publication") or ""
    venue_txt = re.split(r"\s\d", pub, maxsplit=1)[0]
    vol = (re.search(r"\b(\d+)\s*\(", pub) or re.search(r"\b(\d+)\b", pub[len(venue_txt):]) or [None, None])[1]
    year = int(article["year"]) if str(article.get("year", "")).isdigit() else None
    best, best_score = None, 0.0
    for w in works:
        s = overlap(st, fold_tokens(w["title"]))
        same_place = (year == w["year"] and overlap(fold_tokens(venue_txt), fold_tokens(w["venue"])) >= 0.6
                      and vol and str(w["volume"]) == vol)
        if same_place:
            s = max(s, 0.9)
        if year and w["year"] and abs(year - w["year"]) > 1:
            s -= 0.3
        if s > best_score:
            best, best_score = w, s
    return best if best_score >= 0.6 else None


def from_scholar(cfg, works):
    author = scholar_id(cfg.get("scholar_author_id"))
    key = serpapi_key()
    if not author or not key:
        print("Google Scholar: skipped (needs scholar_author_id in the config and a SerpApi key).")
        return None
    mock = os.environ.get("SERPAPI_MOCK")
    if mock:
        data = json.load(open(mock, encoding="utf-8"))
    else:
        q = urllib.parse.urlencode({"engine": "google_scholar_author", "author_id": author,
                                    "num": 100, "sort": "pubdate", "api_key": key})
        try:
            data = get_json(f"https://serpapi.com/search.json?{q}")
        except ApiLimit as e:
            print(f"  ! SerpApi request failed: {str(e).replace(key, '***')}", file=sys.stderr)
            return None
    if not data or data.get("error"):
        print(f"  ! SerpApi: {(data or {}).get('error', 'no data')}", file=sys.stderr)
        return None

    table = (data.get("cited_by") or {}).get("table") or []
    def row(name):
        for r in table:
            if name in r:
                return r[name]
        return {}
    since_key = next((k for k in row("citations") if k.startswith("since")), "")
    articles = data.get("articles") or []
    matched, unmatched = 0, []
    for a in articles:
        n = ((a.get("cited_by") or {}).get("value")) or 0
        w = match_scholar(a, works)
        if w:
            w["scholar_citations"] = max(n, w.get("scholar_citations", 0))
            w["scholar_link"] = a.get("link", "")
            matched += 1
        else:
            unmatched.append({"title": a.get("title"), "year": a.get("year"), "cited_by": n})
    print(f"  {len(articles)} Scholar articles, {matched} matched to the publication list")
    for u in unmatched:
        print(f"  - not matched: {u['title'][:70]} ({u['year']}, cited {u['cited_by']})")
    return {
        "author_id": author,
        "citations": row("citations").get("all", 0),
        "citations_since": row("citations").get(since_key, 0), "since": since_key.replace("since_", ""),
        "h_index": row("h_index").get("all", 0),
        "i10_index": row("i10_index").get("all", 0),
        "by_year": {str(g["year"]): g["citations"] for g in (data.get("cited_by") or {}).get("graph") or []},
        "unmatched": unmatched,
    }


# ------------------------------------------------------------------ main
def title_key(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())[:80]


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    cfg["_orcid"] = norm_orcid(cfg.get("orcid"))
    exclude = {norm_doi(d) for d in cfg.get("exclude_dois", [])}
    exclude_ids = {i.rsplit("/", 1)[-1].upper() for i in cfg.get("exclude_openalex_ids", [])}

    works = []
    if cfg["_orcid"]:
        print(f"OpenAlex: works for ORCID {cfg['_orcid']} ...")
        works = from_openalex(cfg)
        print(f"  {len(works)} found")
    else:
        print("No ORCID in config: skipping OpenAlex and ORCID.")

    orcid_dois = {}
    if cfg["_orcid"]:
        print("ORCID: public record ...")
        orcid_dois, orcid_works = from_orcid(cfg)
        works += orcid_works
        print(f"  {len(orcid_dois) + len(orcid_works)} found ({len(orcid_works)} without DOI)")

    have = {w["doi"] for w in works if w["doi"]}
    extra = []
    for d in list(orcid_dois) + cfg.get("extra_dois", []):
        d = norm_doi(d)
        if d and d not in have and d not in extra:
            extra.append(d)
    if extra:
        print(f"Crossref: {len(extra)} extra DOI(s) ...")
    for doi in extra:
        w = from_crossref(doi, cfg)
        if w and doi in orcid_dois:
            # Prefer what was typed into ORCID (often the English title); keep the other one as an alt title.
            o = orcid_dois[doi]
            if o["title"] and o["title"].lower() != w["title"].lower():
                w["alt_title"], w["title"] = w["title"], o["title"]
            if o["venue"] and w["type"] in BOOK_TYPES:
                w["venue"] = o["venue"]
        if w:
            works.append(w)
        time.sleep(0.2)

    # De-duplicate (same DOI, or same title e.g. preprint + published version: keep the one with a DOI/venue).
    def score(w):
        return (bool(w["doi"]), bool(w["venue"]), w["type"] != "preprint", w["citations"])

    unique, index = [], {}  # index: DOI or title key -> position in unique
    for w in works:
        oa_id = (w.get("openalex_id") or "").rsplit("/", 1)[-1].upper()
        if w["doi"] in exclude or oa_id in exclude_ids or not w["title"]:
            continue
        keys = [k for k in (w["doi"], title_key(w["title"])) if k]
        pos = next((index[k] for k in keys if k in index), None)
        if pos is None:
            pos = len(unique)
            unique.append(w)
        elif score(w) > score(unique[pos]):
            unique[pos] = w
        for k in keys:
            index[k] = pos
    unique.sort(key=lambda w: (w["year"] or 0, w["date"]), reverse=True)

    for w in unique:
        w["venue"] = w["venue"] or venue_from_doi(w["doi"])
        w["section"] = "books" if w["type"] in BOOK_TYPES else "research"

    print("Google Scholar (SerpApi) ...")
    scholar = from_scholar(cfg, unique)
    if scholar is None and os.path.exists(OUTPUT):
        # Keep the last good Scholar figures rather than dropping them when the request fails.
        old = json.load(open(OUTPUT, encoding="utf-8"))
        scholar = old.get("scholar")
        if scholar:
            print(f"  using previous Scholar figures from {old.get('scholar_updated', 'an earlier run')}")
            prev = {title_key(w["title"]): w for w in old.get("works", [])}
            for w in unique:
                p = prev.get(title_key(w["title"]))
                if p and "scholar_citations" in p:
                    w["scholar_citations"], w["scholar_link"] = p["scholar_citations"], p.get("scholar_link", "")

    out = {"updated": date.today().isoformat(), "orcid": cfg["_orcid"], "works": unique}
    if scholar:
        out["scholar"] = scholar
        out["scholar_updated"] = scholar.get("fetched") or date.today().isoformat()
        scholar.setdefault("fetched", out["scholar_updated"])
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n_r = sum(w["section"] == "research" for w in unique)
    print(f"Saved {len(unique)} works ({n_r} research, {len(unique) - n_r} books) to content/publications.json")


if __name__ == "__main__":
    main()
