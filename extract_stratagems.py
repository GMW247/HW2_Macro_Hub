"""Extract stratagem codes from a saved Helldivers wiki "Stratagems" page into data/stratagems.json (+ .csv).

Usage:
    python extract_stratagems.py path\\to\\Stratagems_-_The_Helldivers_Wiki.html

Save the page https://helldivers.wiki.gg/wiki/Stratagems from your browser ("Save page as", complete
or HTML only) and pass the .html file.
"""
import csv
import html
import json
import pathlib
import re
import sys

here = pathlib.Path(__file__).resolve().parent
if len(sys.argv) != 2:
    sys.exit(__doc__)
t = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
t = re.sub(r'data:image[^"\']+', 'D', t)  # drop inline images
DIR = {"Up": "U", "Down": "D", "Left": "L", "Right": "R"}
out = []
# walk headings and tables in document order to track category context
tok = re.compile(r'<h3>.*?id="([^"]+)"|<summary>(.*?)</summary>|<table.*?</table>', re.S)
permit = sub = None
for m in tok.finditer(t):
    if m.group(1):
        permit = m.group(1).replace("_", " ")
        sub = None
        continue
    if m.group(2) is not None:
        sub = re.sub(r'<.*?>', '', m.group(2)).strip()
        continue
    tbl = m.group(0)
    if "Stratagem Code" not in tbl:
        continue
    for row in re.findall(r'<tr>(.*?)</tr>', tbl, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) < 3:
            continue

        def cell(i):
            return html.unescape(re.sub(r'<.*?>', '', tds[i])).strip() if len(tds) > i else ""

        arrows = re.findall(r'alt="Stratagem Arrow (\w+)', tds[2])
        out.append({"name": cell(1), "code": "".join(DIR[a] for a in arrows), "permit": permit,
                    "category": sub, "cooldown": cell(3), "cost": cell(4), "unlock": cell(5)})

# Drop exact duplicates; disambiguate same name with different codes by suffixing the code.
seen, uniq = set(), []
for o in out:
    if (o["name"], o["code"]) not in seen:
        seen.add((o["name"], o["code"]))
        uniq.append(o)
codes_by_name = {}
for o in uniq:
    codes_by_name.setdefault(o["name"], []).append(o)
for name, rows in codes_by_name.items():
    if len(rows) > 1:
        for o in rows:
            o["name"] = f"{name} ({o['code']})"
out = uniq
if not out:
    sys.exit("No stratagem tables found in that file.")

(here / "data").mkdir(exist_ok=True)
with open(here / "data" / "stratagems.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
with open(here / "data" / "stratagems.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)
print(len(out), "stratagems;", sum(1 for o in out if not o["code"]), "without code")
