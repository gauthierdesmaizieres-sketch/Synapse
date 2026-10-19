"""Auto-test : python collector/test_collect.py"""
import collect

items = [{"title": "a"}, {"title": "b"}]
digest = collect.apply_ai(items, {"digest": " • point ", "items": [
    {"i": 0, "resume": " Résumé A "}, {"i": 5, "resume": "hors limites"}, {"i": "1", "resume": "mauvais type"}]})
assert digest == "• point"
assert items[0]["ai"] == "Résumé A" and "ai" not in items[1]
assert collect.apply_ai(items, {}) is None
print("ok")
