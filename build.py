#!/usr/bin/env python3
"""Regenerate the Publications list in index.html from OpenAlex.

Pulls Stijn Peeters' works (OpenAlex author A5088653307), keeps only published
journal articles / reviews that have a DOI, and rewrites the block between the
<!-- PUBLICATIONS:START --> and <!-- PUBLICATIONS:END --> markers in index.html.
Also refreshes the "Last updated <Month Year>" line in the footer.

Standard library only, no dependencies.  Run:  python build.py
"""
import json, re, html, urllib.request, urllib.parse, datetime, pathlib, sys

AUTHOR_ID = "A5088653307"
MAILTO = "stijn1.peeters@wur.nl"
HERE = pathlib.Path(__file__).parent
INDEX = HERE / "index.html"

# Turn <sub>2</sub> / <sup>3</sup> into real unicode so "CO<sub>2</sub>" -> "CO2".
SUB = str.maketrans("0123456789+-=()n", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₙ")
SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")

# Venues that indicate a preprint server / dataset repository, not a publication.
BAD_VENUE = ("repository", "biorxiv", "egusphere", "archiving", "figshare", "zenodo")


def clean(t):
    t = t or ""
    t = re.sub(r"\s*<sub>(.*?)</sub>", lambda m: m.group(1).translate(SUB), t, flags=re.I)
    t = re.sub(r"\s*<sup>(.*?)</sup>", lambda m: m.group(1).translate(SUP), t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)              # strip remaining tags
    t = html.unescape(t)
    t = t.replace("�", "")                # drop replacement chars (mojibake)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:])", r"\1", t)       # no space before punctuation
    t = re.sub(r"([‘“])\s+", r"\1", t)         # no space after an opening curly quote
    t = re.sub(r"\s+([’”])", r"\1", t)         # no space before a closing curly quote
    return t


def esc(s):
    return html.escape(s, quote=True)


def source_of(w):
    return (w.get("primary_location") or {}).get("source") or {}


def keep(w):
    if w.get("type") not in ("article", "review"):
        return False
    if not w.get("doi"):
        return False
    venue = (source_of(w).get("display_name") or "").lower()
    return not any(b in venue for b in BAD_VENUE)


def fetch_works():
    base = "https://api.openalex.org/works"
    common = {
        "filter": f"author.id:{AUTHOR_ID}",
        "per-page": "200",
        "sort": "publication_date:desc",
        "mailto": MAILTO,
    }
    out, cursor = [], "*"
    while cursor:
        url = base + "?" + urllib.parse.urlencode(dict(common, cursor=cursor))
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.load(r)
        out.extend(data["results"])
        if not data["results"]:
            break
        cursor = data["meta"].get("next_cursor")
    return out


def authors_html(w):
    names = []
    for a in w.get("authorships", []):
        nm = a["author"]["display_name"]
        names.append(f"<strong>{esc(nm)}</strong>" if ("Peeters" in nm and "Stijn" in nm) else esc(nm))
    return ", ".join(names)


def build_block(works):
    pubs = [w for w in works if keep(w)]
    pubs.sort(key=lambda w: (-(w.get("publication_year") or 0), clean(w["display_name"]).lower()))
    lines, year = [], None
    for w in pubs:
        y = w.get("publication_year")
        if y != year:
            year = y
            lines.append(f"    <h2>{y}</h2>")
        title = clean(w["display_name"])
        venue = clean(source_of(w).get("display_name") or "")
        lines.append('    <div class="pub">')
        lines.append(f'      <a class="title" href="{esc(w["doi"])}">{esc(title)}</a>')
        lines.append(f'      <div class="authors">{authors_html(w)}</div>')
        lines.append(f'      <div class="meta"><em>{esc(venue)}</em></div>')
        lines.append("    </div>")
    return "\n".join(lines), len(pubs)


def main():
    works = fetch_works()
    block, n = build_block(works)
    text = INDEX.read_text(encoding="utf-8")

    pat = re.compile(r"(<!-- PUBLICATIONS:START.*?-->\n).*?(\n[ \t]*<!-- PUBLICATIONS:END -->)", re.S)
    if not pat.search(text):
        sys.exit("Could not find PUBLICATIONS:START / PUBLICATIONS:END markers in index.html")
    text = pat.sub(lambda m: m.group(1) + block + m.group(2), text)

    month = datetime.date.today().strftime("%B %Y")
    text = re.sub(r"Last updated [^.]*\.", f"Last updated {month}.", text)

    INDEX.write_text(text, encoding="utf-8")
    print(f"Wrote {n} publications. Footer set to: Last updated {month}.")


if __name__ == "__main__":
    main()
