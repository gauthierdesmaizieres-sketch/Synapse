"""Collecte une nouvelle édition du fil et l'écrit dans docs/data/.

Usage : python collector/collect.py
Bibliothèque standard uniquement (aucune dépendance à installer).
Variables d'environnement optionnelles :
  S2_API_KEY      clé Semantic Scholar gratuite -> résumés "TL;DR" d'une phrase
  OPENALEX_MAILTO ton email, pour le "polite pool" OpenAlex (plus rapide)
"""
import html
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
UA = "SynapseNewsBot/1.0 (personal science digest; +https://github.com)"
TODAY = date.today()


# ---------------------------------------------------------------- utilitaires

def fetch(url, data=None, headers=None, timeout=30, retries=2):
    h = {"User-Agent": UA, **(headers or {})}
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # réseau capricieux : on réessaie puis on abandonne la source
            if attempt == retries:
                print(f"  ! échec {url[:90]} : {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def fetch_json(url, **kw):
    raw = fetch(url, **kw)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def clean(text):
    """Retire le HTML, garde les intertitres d'abstract sous forme 'Titre: '."""
    if not text:
        return ""
    text = re.sub(r"<h\d[^>]*>(.*?)</h\d>", r" \1: ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def shorten(text, limit=config.SUMMARY_CHARS):
    text = re.sub(r"^(abstract|summary)\b[\s:.]*", "", text.strip(), flags=re.I).lstrip(":;.,- ")
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if end > limit * 0.55:
        return cut[: end + 1]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "…"


CONCLUSION_RE = re.compile(
    r"\b(conclusions?|interpretation|significance|implications|in conclusion)\s*[:.]\s*", re.I)
SECTION_RE = re.compile(
    r"\b(background|introduction|objectives?|aims?|purpose|methods?|design|results?|findings|"
    r"participants|setting|trial registration|funding|keywords?)\s*:\s", re.I)


def summarize_abstract(abstract):
    """Résumé gratuit sans IA : la conclusion d'un abstract structuré, sinon son début."""
    abstract = re.sub(r"^(abstract|summary)\b[\s:.]*", "", clean(abstract), flags=re.I)
    m = None
    for m in CONCLUSION_RE.finditer(abstract):
        pass  # on garde la dernière occurrence (la vraie section finale)
    if m and m.end() < len(abstract) - 40:
        concl = abstract[m.end():]
        nxt = SECTION_RE.search(concl)
        if nxt:
            concl = concl[: nxt.start()]
        return shorten(concl)
    first = SECTION_RE.sub("", abstract, count=1) if SECTION_RE.match(abstract) else abstract
    return shorten(first)


def norm_id(doi=None, url=None):
    if doi:
        return "doi:" + doi.lower().replace("https://doi.org/", "")
    return "url:" + (url or "").split("?")[0].rstrip("/")


def journal_bonus(name):
    n = (name or "").lower().strip()
    for j in config.TOP_JOURNALS:
        if n == j or n.startswith(j + " ") or n.startswith("the " + j):
            return 3
    return 0


ANIMAL_RE = re.compile(r"\b(mice|mouse|murine|rats?|rodents?|zebrafish|drosophila|in vitro|c\. elegans)\b", re.I)
PROTOCOL_RE = re.compile(r"\b(study protocol|protocol for|trial protocol|erratum|corrigendum|retraction)\b", re.I)


# ---------------------------------------------------------------- sources RSS

MEDIA = "{http://search.yahoo.com/mrss/}"


def parse_feed(url):
    raw = fetch(url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    site = urllib.parse.urlparse(url).netloc.replace("www.", "").replace("api.", "")
    site = {"phys.org": "Phys.org", "medicalxpress.com": "Medical Xpress", "techxplore.com": "Tech Xplore",
            "quantamagazine.org": "Quanta Magazine"}.get(site, site)
    out = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        img = None
        for tag in ("thumbnail", "content"):
            el = it.find(MEDIA + tag)
            if el is not None and el.get("url"):
                img = el.get("url")
                break
        if img is None:
            enc = it.find("enclosure")
            if enc is not None and (enc.get("type") or "").startswith("image"):
                img = enc.get("url")
        if img and "/news/tmb/" in img:  # miniature 90px Science X -> version 800px
            img = img.replace("/news/tmb/", "/news/800a/")
        try:
            d = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        except Exception:
            d = TODAY.isoformat()
        desc = re.sub(r"The post .* appeared first on .*$", "", clean(it.findtext("description")))
        out.append({
            "id": norm_id(url=link), "kind": "vulga", "title": title,
            "summary": shorten(desc), "image": img, "url": link, "source": site,
            "date": d, "tags": ["Vulgarisation"], "oa": None,
        })
    return out


# ---------------------------------------------------------------- Europe PMC

def epmc_search(query, since):
    q = f"({query}) AND FIRST_PDATE:[{since} TO {TODAY}] AND HAS_ABSTRACT:y"
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
           + urllib.parse.urlencode({"query": q, "format": "json", "resultType": "core", "pageSize": 60}))
    d = fetch_json(url)
    out = []
    for r in (d or {}).get("resultList", {}).get("result", []):
        types = [t.lower() for t in r.get("pubTypeList", {}).get("pubType", [])]
        is_pre = r.get("source") == "PPR" or "preprint" in types
        journal = (r.get("journalInfo", {}).get("journal", {}) or {}).get("title") \
            or (r.get("bookOrReportDetails", {}) or {}).get("publisher") or ("Préprint" if is_pre else "")
        doi = r.get("doi")
        oa = None
        for u in r.get("fullTextUrlList", {}).get("fullTextUrl", []):
            if u.get("availabilityCode") in ("OA", "F") and u.get("url"):
                oa = {"url": u["url"], "label": "Texte intégral gratuit"}
                break
        if not oa and r.get("pmcid") and r.get("isOpenAccess") == "Y":
            oa = {"url": f"https://europepmc.org/article/PMC/{r['pmcid']}", "label": "Texte intégral gratuit"}
        if not oa and is_pre and doi:
            oa = {"url": f"https://doi.org/{doi}", "label": "Préprint gratuit"}
        link = f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}"
        out.append(make_paper(
            doi=doi, url=link, title=clean(r.get("title")), abstract=r.get("abstractText", ""),
            journal=journal, d=r.get("firstPublicationDate"), types=types, preprint=is_pre, oa=oa))
    return out


# ---------------------------------------------------------------- OpenAlex

def openalex_params(extra):
    p = dict(extra)
    if os.environ.get("OPENALEX_MAILTO"):
        p["mailto"] = os.environ["OPENALEX_MAILTO"]
    return urllib.parse.urlencode(p, safe=":,|/")


def inverted_to_text(inv):
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def oa_from_openalex(w):
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    url = best.get("pdf_url") or best.get("landing_page_url") or oa.get("oa_url")
    if oa.get("is_oa") and url:
        return {"url": url, "label": "Texte intégral gratuit"}
    return None


def openalex_field(field_id, since):
    params = openalex_params({
        "filter": (f"from_publication_date:{since},to_publication_date:{TODAY},type:article,"
                   f"has_abstract:true,primary_topic.field.id:{field_id},primary_location.source.is_core:true"),
        "per_page": 80,
        "select": "id,doi,title,publication_date,primary_location,open_access,best_oa_location,abstract_inverted_index",
    })
    d = fetch_json("https://api.openalex.org/works?" + params)
    out = []
    for w in (d or {}).get("results", []):
        src = ((w.get("primary_location") or {}).get("source") or {})
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        out.append(make_paper(
            doi=doi, url=w.get("doi") or w["id"], title=clean(w.get("title")),
            abstract=inverted_to_text(w.get("abstract_inverted_index")), journal=src.get("display_name", ""),
            d=w.get("publication_date"), types=[], preprint=False, oa=oa_from_openalex(w)))
    return out


def enrich_oa(papers):
    """Pour les papiers sans lien gratuit connu : demande à OpenAlex (données Unpaywall)."""
    todo = [p for p in papers if not p["oa"] and p.get("_doi")]
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        dois = "|".join("https://doi.org/" + p["_doi"] for p in chunk)
        d = fetch_json("https://api.openalex.org/works?" + openalex_params({
            "filter": "doi:" + dois, "per_page": 50, "select": "doi,open_access,best_oa_location"}))
        found = {(w.get("doi") or "").lower(): w for w in (d or {}).get("results", [])}
        for p in chunk:
            w = found.get("https://doi.org/" + p["_doi"].lower())
            if w:
                p["oa"] = oa_from_openalex(w)


def add_tldr(papers):
    """Résumés d'une phrase de Semantic Scholar, seulement si une clé API est fournie."""
    key = os.environ.get("S2_API_KEY")
    with_doi = [p for p in papers if p.get("_doi")]
    if not key or not with_doi:
        return
    body = json.dumps({"ids": ["DOI:" + p["_doi"] for p in with_doi]}).encode()
    raw = fetch("https://api.semanticscholar.org/graph/v1/paper/batch?fields=tldr", data=body,
                headers={"Content-Type": "application/json", "x-api-key": key})
    try:
        res = json.loads(raw) if raw else []
    except ValueError:
        return
    for p, r in zip(with_doi, res):
        tldr = ((r or {}).get("tldr") or {}).get("text")
        if tldr:
            p["summary"] = shorten(tldr)
            p["tags"].append("TL;DR")


AI_PROMPT = """Tu prépares le fil d'actualité scientifique personnel d'un passionné de chimie, biochimie,
médicaments et musculation. Voici les {n} articles de l'édition (JSON).

Réponds UNIQUEMENT avec un objet JSON de la forme :
{{"digest": "...", "items": [{{"i": 0, "resume": "..."}}, ...]}}

- "resume" (un par article, même "i") : 2 phrases en français, 50 mots maximum. Dis ce qui a été
  découvert et pourquoi c'est intéressant, avec le chiffre clé s'il y en a un. Ton technique pour
  les domaines chimie et biochimie, vulgarisé mais précis pour les autres. Si c'est une étude
  animale, in vitro ou un préprint, signale-le en quelques mots.
- "digest" : 4 à 6 puces (une par ligne, commençant par "• ") qui résument les temps forts de
  l'édition, pour savoir en 20 secondes ce qui vaut la peine d'être lu.
N'invente rien qui ne soit pas dans les textes fournis.

Articles :
{articles}"""


def ai_summaries(items):
    """Résumés en français + digest de l'édition via Gemini (palier gratuit). Sans clé : rien."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not items:
        return None
    articles = json.dumps([{"i": i, "domaine": it["domain"], "type": it["kind"], "titre": it["title"],
                            "texte": it.get("_abstract") or it["summary"]} for i, it in enumerate(items)],
                          ensure_ascii=False)
    body = json.dumps({
        "contents": [{"parts": [{"text": AI_PROMPT.format(n=len(items), articles=articles)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    raw = fetch(url, data=body, timeout=120,
                headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        text = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
        return apply_ai(items, json.loads(text))
    except (TypeError, ValueError, KeyError, IndexError) as e:
        print(f"  ! résumés IA ignorés : {e}", file=sys.stderr)
        return None


def apply_ai(items, data):
    for r in data.get("items", []):
        i = r.get("i")
        if isinstance(i, int) and 0 <= i < len(items) and r.get("resume"):
            items[i]["ai"] = r["resume"].strip()
    return (data.get("digest") or "").strip() or None


# ---------------------------------------------------------------- papiers : forme commune + score

def make_paper(doi, url, title, abstract, journal, d, types, preprint, oa):
    text = f"{title} {clean(abstract)}"
    tags, score = [], 0.0
    tl = " ".join(types) + " " + title.lower()
    if "meta-analysis" in tl or "meta analysis" in tl:
        tags.append("Méta-analyse"); score += 4
    elif "systematic review" in tl:
        tags.append("Revue systématique"); score += 3
    elif "randomized controlled trial" in tl or "randomised" in tl or "randomized" in tl:
        tags.append("Essai randomisé"); score += 3
    elif "review" in types or re.search(r"\breview\b", title, re.I):
        tags.append("Revue"); score += 1
    if preprint:
        tags.append("Préprint"); score -= 1
    if ANIMAL_RE.search(text):
        tags.append("Animal / in vitro"); score -= 1
    if PROTOCOL_RE.search(title):
        score -= 10
    score += journal_bonus(journal)
    if oa:
        score += 1
    if len(clean(abstract)) < 200:
        score -= 2
    return {
        "id": norm_id(doi=doi, url=url), "kind": "paper", "title": title,
        "summary": summarize_abstract(abstract), "image": None, "url": url,
        "source": journal or "Article", "date": (d or TODAY.isoformat())[:10],
        "tags": tags, "oa": oa, "_score": score + random.random() * 0.5, "_doi": doi,
        "_abstract": clean(abstract)[:1500],
    }


# ---------------------------------------------------------------- assemblage de l'édition

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def pick(items, n, seen, taken):
    out = []
    for it in items:
        if len(out) >= n:
            break
        if it["id"] in seen or it["id"] in taken or not it["title"]:
            continue
        taken.add(it["id"])
        out.append(it)
    return out


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "editions").mkdir(exist_ok=True)
    index = load_json(DATA / "index.json", {"editions": []})
    seen = set(load_json(DATA / "seen.json", []))

    if index["editions"]:
        last = date.fromisoformat(index["editions"][0])
        days = max(4, min(14, (TODAY - last).days + 1))
    else:
        days = config.LOOKBACK_DAYS
    since = (TODAY - timedelta(days=days)).isoformat()
    random.seed(TODAY.toordinal())
    print(f"Édition du {TODAY} — fenêtre depuis {since}")

    feed_urls = sorted({u for d in config.DOMAINS for u in d.get("feeds", [])} | set(config.EXOTIC["feeds"]))
    with ThreadPoolExecutor(8) as ex:
        feeds = dict(zip(feed_urls, ex.map(parse_feed, feed_urls)))
        jobs = {}
        for dom in config.DOMAINS:
            if dom.get("epmc"):
                jobs[dom["id"]] = ex.submit(epmc_search, dom["epmc"], since)
            elif dom.get("openalex"):
                jobs[dom["id"]] = ex.submit(openalex_field, dom["openalex"], since)
        papers_by_dom = {k: f.result() for k, f in jobs.items()}

    taken, items = set(), []
    for dom in config.DOMAINS:
        vulga = sorted((it for u in dom.get("feeds", []) for it in feeds.get(u, [])
                        if it["date"] >= since), key=lambda x: x["date"], reverse=True)
        kw = [k.lower() for k in dom.get("keywords", [])]
        if kw:  # les articles qui parlent vraiment du domaine passent devant (tri stable : récents d'abord)
            vulga.sort(key=lambda x: 2 * sum(k in x["title"].lower() for k in kw)
                       + sum(k in x["summary"].lower() for k in kw), reverse=True)
        chosen = pick(vulga, dom["vulga"], seen, taken)
        papers = sorted(papers_by_dom.get(dom["id"], []), key=lambda p: p["_score"], reverse=True)
        chosen += pick(papers, dom["papers"], seen, taken)
        for it in chosen:
            it["domain"] = dom["id"]
        print(f"  {dom['label']:<18} {len(vulga):>3} vulga, {len(papers):>3} papiers -> {len(chosen)} cartes")
        items += chosen

    # une carte par flux "exotique" différent, flux tirés au hasard
    exotic_feeds = list(config.EXOTIC["feeds"])
    random.shuffle(exotic_feeds)
    n_exotic = 0
    for u in exotic_feeds:
        if n_exotic >= config.EXOTIC["count"]:
            break
        pool = [it for it in feeds.get(u, []) if it["date"] >= since]
        random.shuffle(pool)
        for it in pick(pool, 1, seen, taken):
            it["domain"] = "exotique"
            items.append(it)
            n_exotic += 1

    papers = [it for it in items if it["kind"] == "paper"]
    enrich_oa(papers)
    add_tldr(papers)
    digest = ai_summaries(items)
    for it in items:
        it.pop("_score", None)
        it.pop("_doi", None)
        it.pop("_abstract", None)

    if not items:
        print("Aucune carte trouvée, édition non écrite.")
        return 1

    edition = {
        "date": TODAY.isoformat(),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domains": [{k: d[k] for k in ("id", "label", "emoji", "color")} for d in config.DOMAINS]
        + [{"id": "exotique", "label": "Hors sentiers", "emoji": "🧭", "color": "#a16207"}],
        "digest": digest,
        "items": items,
    }
    (DATA / "editions" / f"{TODAY}.json").write_text(
        json.dumps(edition, ensure_ascii=False, indent=1), encoding="utf-8")

    eds = [TODAY.isoformat()] + [e for e in index["editions"] if e != TODAY.isoformat()]
    for old in eds[config.MAX_EDITIONS:]:
        (DATA / "editions" / f"{old}.json").unlink(missing_ok=True)
    (DATA / "index.json").write_text(json.dumps({"editions": eds[: config.MAX_EDITIONS]}, indent=1), encoding="utf-8")
    old_seen = load_json(DATA / "seen.json", [])
    seen_list = (old_seen + [i for i in taken if i not in seen])[-4000:]
    (DATA / "seen.json").write_text(json.dumps(seen_list), encoding="utf-8")
    print(f"OK : {len(items)} cartes écrites dans docs/data/editions/{TODAY}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
