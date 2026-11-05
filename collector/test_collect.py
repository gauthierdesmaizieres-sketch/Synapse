"""Auto-test : python collector/test_collect.py"""
import collect

items = [{"title": "a"}, {"title": "b"}]
digest = collect.apply_ai(items, {"digest": " • point ", "items": [
    {"i": 0, "resume": " Résumé A "}, {"i": 5, "resume": "hors limites"}, {"i": "1", "resume": "mauvais type"}]})
assert digest == "• point"
assert items[0]["ai"] == "Résumé A" and "ai" not in items[1]
assert collect.apply_ai(items, {}) is None

import huberman  # noqa: E402

rss = b"""<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
<item><title>Old</title><link>https://h/old</link><pubDate>Mon, 02 Nov 2026 09:00:00 -0000</pubDate>
<enclosure url="https://a/old.mp3"/></item>
<item><title>Sleep &amp; Light</title><link>https://h/new</link><pubDate>Wed, 04 Nov 2026 09:00:00 -0000</pubDate>
<itunes:duration>7200</itunes:duration><enclosure url="https://a/new.mp3"/>
<itunes:summary>Timestamps (00:00:00) Intro (00:05:10) Sponsor: AG1 (01:02:03) Morning light, Tools</itunes:summary></item>
</channel></rss>"""
feed = huberman.parse_feed(rss)
assert [e["id"] for e in feed] == ["https://h/new", "https://h/old"] and feed[0]["duration"] == 7200
assert [c["t"] for c in feed[0]["chapters"]] == ["00:00:00", "01:02:03"]  # sponsor retiré
data = {"episodes": [], "failed": {"https://h/new": 3}}
assert huberman.next_episode(feed, data)["id"] == "https://h/old"  # 3 échecs : abandonné
data["failed"] = {}
huberman.merge(data, feed[0], {"resume": " R ", "points": ["a", ""], "protocoles": [{"quoi": "x"}, "bad"]})
ep = data["episodes"][0]
assert ep["resume"] == "R" and ep["points"] == ["a"] and ep["protocoles"] == [{"quoi": "x"}]
assert ep["chapitres"] == feed[0]["chapters"]  # chapitres RSS si l'IA n'en donne pas
assert huberman.next_episode(feed, data)["id"] == "https://h/old"
print("ok")
