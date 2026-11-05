"""Onglet Huberman : résume le dernier épisode du podcast Huberman Lab avec Gemini (palier gratuit).

Lancement : python collector/huberman.py   (sans GEMINI_API_KEY : affiche l'épisode à traiter, n'écrit rien)
Un seul épisode par lancement : l'audio d'un épisode de 3 h pèse ~350 000 tokens, le gratuit n'en avale pas deux d'affilée.
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import collect
import config

OUT = collect.DATA / "huberman.json"
API = "https://generativelanguage.googleapis.com"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
CHAPTER_RE = re.compile(r"\((\d{1,2}:\d{2}(?::\d{2})?)\)\s*([^\n(]+)")

PROMPT = """Tu écoutes un épisode du podcast Huberman Lab : « {title} ».
Chapitres officiels :
{chapters}

Réponds uniquement en JSON, en français, avec exactement ces clés :
{{"resume": "3 à 4 phrases : de quoi parle l'épisode et la conclusion principale",
 "points": ["5 idées clés au maximum, une phrase chacune"],
 "protocoles": [{{"quoi": "action concrète", "comment": "dose, durée, moment de la journée, précautions"}}],
 "chapitres": [{{"t": "horodatage tel quel", "titre": "titre traduit en français"}}]}}
- protocoles : seulement ce qui est explicitement recommandé dans l'épisode (liste vide sinon), 6 au maximum.
- chapitres : reprends les chapitres officiels ci-dessus, sans ceux des sponsors.
- Reformule avec tes mots, pas de longues citations. N'invente rien qui ne soit pas dans l'épisode."""


def parse_feed(xml_bytes):
    """Épisodes du flux RSS, du plus récent au plus ancien."""
    eps = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        enc = it.find("enclosure")
        link = (it.findtext("link") or "").strip()
        if enc is None or not link:
            continue
        notes = it.findtext(f"{ITUNES}summary") or it.findtext("description") or ""
        chapters = [{"t": t, "titre": html.unescape(c).strip()} for t, c in CHAPTER_RE.findall(notes)
                    if not re.match(r"sponsors?\b", c.strip(), re.I)]
        try:
            d = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        except (TypeError, ValueError):
            d = collect.TODAY.isoformat()
        eps.append({"id": link, "title": html.unescape(it.findtext("title") or "").strip(), "url": link,
                    "date": d, "duration": int(it.findtext(f"{ITUNES}duration") or 0),
                    "audio": enc.get("url"), "chapters": chapters})
    return sorted(eps, key=lambda e: e["date"], reverse=True)


def next_episode(feed, data):
    """Le plus récent des épisodes gardés qui n'est ni résumé ni abandonné après 3 échecs."""
    done = {e["id"] for e in data["episodes"]}
    for ep in feed[: config.HUBERMAN_KEEP]:  # seulement les récents : l'historique tronqué ne se re-remplit pas en boucle
        if ep["id"] not in done and data["failed"].get(ep["id"], 0) < 3:
            return ep
    return None


def merge(data, ep, ai):
    """Ajoute le résumé IA à l'historique (plus récent d'abord, taille bornée)."""
    chapters = [c for c in ai.get("chapitres") or [] if isinstance(c, dict) and c.get("t") and c.get("titre")]
    episode = {k: ep[k] for k in ("id", "title", "url", "date", "duration")} | {
        "resume": str(ai.get("resume") or "").strip(),
        "points": [str(p).strip() for p in ai.get("points") or [] if str(p).strip()][:5],
        "protocoles": [p for p in ai.get("protocoles") or [] if isinstance(p, dict) and p.get("quoi")][:6],
        "chapitres": chapters or ep["chapters"],
    }
    eps = [episode] + [e for e in data["episodes"] if e["id"] != ep["id"]]
    data["episodes"] = sorted(eps, key=lambda e: e["date"], reverse=True)[: config.HUBERMAN_KEEP]
    data["failed"].pop(ep["id"], None)
    return data


def api(method, path, key, body=None, headers=None, timeout=120):
    req = urllib.request.Request(API + path, data=body, method=method,
                                 headers={"x-goog-api-key": key, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.headers, r.read()


def upload(audio, name, key):
    """Files API de Gemini (envoi « resumable »), puis attente que le fichier soit prêt."""
    h, _ = api("POST", "/upload/v1beta/files", key, json.dumps({"file": {"display_name": name[:100]}}).encode(), {
        "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(audio)),
        "X-Goog-Upload-Header-Content-Type": "audio/mpeg", "Content-Type": "application/json"})
    req = urllib.request.Request(h["x-goog-upload-url"], data=audio, method="POST", headers={
        "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"})
    with urllib.request.urlopen(req, timeout=600) as r:
        f = json.loads(r.read())["file"]
    for _ in range(60):
        if f.get("state") != "PROCESSING":
            break
        time.sleep(5)
        f = json.loads(api("GET", f"/v1beta/{f['name']}", key)[1])
    if f.get("state") != "ACTIVE":
        raise RuntimeError(f"fichier audio refusé par Gemini : {f.get('state')}")
    return f


def summarize(ep, key):
    audio = collect.fetch(ep["audio"], timeout=600)
    if not audio:
        return None
    print(f"  audio : {len(audio) / 1e6:.0f} Mo")
    f = upload(audio, ep["title"], key)
    chapters = "\n".join(f"({c['t']}) {c['titre']}" for c in ep["chapters"]) or "(aucun)"
    body = json.dumps({
        "contents": [{"parts": [{"file_data": {"mime_type": "audio/mpeg", "file_uri": f["uri"]}},
                                {"text": PROMPT.format(title=ep["title"], chapters=chapters)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    try:
        for model in config.GEMINI_MODELS:  # même logique que les résumés d'articles : réessais puis modèle de secours
            for wait in (0, 60):
                time.sleep(wait)
                try:
                    raw = api("POST", f"/v1beta/models/{model}:generateContent", key, body,
                              {"Content-Type": "application/json"}, timeout=600)[1]
                    text = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"  résumé IA : {model}")
                    return json.loads(text)
                except Exception as e:  # 429 (quota de tokens/minute) ou 503 (surcharge) : on réessaie
                    print(f"  ! {model} : {e}", file=sys.stderr)
        return None
    finally:
        try:
            api("DELETE", f"/v1beta/{f['name']}", key)
        except Exception:
            pass  # Gemini efface de toute façon les fichiers après 48 h


def main():
    data = collect.load_json(OUT, {})
    data = {"episodes": data.get("episodes", []), "failed": data.get("failed", {})}
    raw = collect.fetch(config.HUBERMAN_FEED)
    if not raw:
        return 0  # flux injoignable : on retentera au prochain passage
    ep = next_episode(parse_feed(raw), data)
    if not ep:
        print("Huberman : rien de nouveau")
        return 0
    print(f"Huberman : {ep['title']} ({ep['duration'] // 60} min)")
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("  (pas de GEMINI_API_KEY : rien n'est écrit)")
        return 0
    try:
        ai = summarize(ep, key)
    except Exception as e:
        print(f"  ! {e}", file=sys.stderr)
        ai = None
    if ai:
        merge(data, ep, ai)
        print("  OK : résumé ajouté")
    else:
        data["failed"][ep["id"]] = data["failed"].get(ep["id"], 0) + 1
        print("  ! résumé raté, nouvel essai au prochain passage", file=sys.stderr)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
