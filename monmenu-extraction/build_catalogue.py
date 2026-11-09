#!/usr/bin/env python3
"""Extract Mon Menu 2025 dishes into a structured catalogue."""
import csv
import json
import re
import unicodedata
from pathlib import Path

W, H = 595.276, 841.89
OCR = Path("/Users/mac/Kaayfi/monmenu-extraction/ocr")
OUT = Path("/Users/mac/Kaayfi/monmenu-extraction")

PLACES = [
    ("Annapurna", [6]),
    ("Aroma Gelato", [8, 9]),
    ("Bambou", [10]),
    ("Be Bey", [12, 13, 14]),
    ("Billy's", [16, 17]),
    ("Brasil Burger", [18, 19]),
    ("Brazilian Pizza", [20]),
    ("Bro's Burger", [22, 23]),
    ("Bro's Kebab", [24]),
    ("Burger & Co", [26]),
    ("Caesar", [28, 29, 30]),
    ("Cake House", [32, 33]),
    ("Casino Sea Plaza", [34]),
    ("Chicken Times", [36, 37]),
    ("Chocolate Sarayi", [38, 39, 40]),
    ("Ciao Italia", [42, 43]),
    ("Coffee Loft", [44, 45]),
    ("Elias", [46]),
    ("Eric Kayser", [48, 49, 50]),
    ("Café Club (FOODLY)", [52]),
    ("Pizza di Roma (FOODLY)", [53]),
    ("Burger House (FOODLY)", [54]),
    ("Shawarma Foodly (FOODLY)", [55]),
    ("Gourmandine", [56, 57]),
    ("Halo", [58, 59]),
    ("Healthy Bar", [60, 61, 62]),
    ("Jeff de Bruges", [66, 67]),
    ("Kebarma", [68, 69]),
    ("L'Epicerie", [70, 71]),
    ("L'Orientale", [72, 73]),
    ("La Baie d'Along", [74, 75]),
    ("La Duchesse", [76, 77]),
    ("La Médine", [78]),
    ("La Pampa", [80, 81]),
    ("La Piazza", [82, 83]),
    ("Le Layal", [84, 85]),
    ("Le Professeur", [86]),
    ("Le Seoul", [88, 89]),
    ("Le Taouk", [90, 91]),
    ("Mamma Pizza", [92, 93]),
    ("Mammy Healthy", [94, 95, 96]),
    ("N'ice Cream", [98]),
    ("Nomad Foodtruck", [100]),
    ("O'Sushi Bar", [102, 103, 104, 105]),
    ("O'Wok Bar", [106, 107]),
    ("Pink Factory", [108, 109]),
    ("Pistache et Noix", [110]),
    ("Pizza Papa", [112, 113]),
    ("Planet Kebab", [114, 115]),
    ("Poz Tacos", [116]),
    ("Quick Automatik", [118]),
    ("Saveurs d'Asie", [120, 121]),
    ("Sen Burger", [122, 123]),
    ("Shawarma Express", [124]),
    ("So Sushi", [126]),
]

SKIP_EXACT = {
    "fcfa", "f", "cfa", "menu", "simple", "nouveau", "new", "scannez",
    "commande", "commandez", "yay", "foodly", "saray menu", "decouvrez le menu",
    "découvrez le menu", "pour le menu complet", "frites et", "boisson",
    "frites et boisson", "choisissez votre pate", "choisissez votre pâte",
}
VARIANT = {"SIMPLE", "MENU", "PM", "MM", "GM", "PETITE", "MOYENNE", "GRANDE",
           "SMALL", "MEDIUM", "LARGE", "MINI"}

PHONE_RE = re.compile(
    r"(\+ ?221\b|\b221\b|\b\d{2}[\s.]\d{3}[\s.]\d{2}[\s.]\d{2}\b|\b\d{2}[\s.]\d{2}[\s.]\d{2}[\s.]\d{2}\b)"
)
PRICE_ONLY_RE = re.compile(
    r"^\+?\s*(?:\d{1,2}[\s.,]\d{3}|\d{3,5})(?:\s*[A-Za-zÀ-ÿ]{1,6})?\s*$"
)
PRICE_FIND_RE = re.compile(
    r"(?<!\d)(\d{1,2}[\s.,]\d{3}|\d{3,5})(?!\d)(?:\s*(?:FCFA|FCA|CFA|F))?",
    re.I,
)
UNIT_AFTER = re.compile(r"^(g|gr|kg|ml|cl|cm|mm|pcs|pc|h|%|l)\b", re.I)


def load_page(page: int):
    path = OCR / f"page_{page:03d}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    lines = []
    for L in data["lines"]:
        t = " ".join(L["t"].split())
        if not t:
            continue
        # Stylised prices often read 0 as O: "5 OOO", "6 O00".
        t = re.sub(
            r"(?<![A-Za-z])(\d{1,2}[\s.]?[Oo0][Oo0\d]{2,3})(?![A-Za-z])",
            lambda m: m.group(1).replace("O", "0").replace("o", "0"),
            t,
        )
        x = L["x"] * W
        w = L["w"] * W
        h = L["h"] * H
        y = (1 - (L["y"] + L["h"])) * H
        lines.append({"t": t, "x": x, "y": y, "w": w, "h": h, "c": L.get("c", 1)})
    return lines


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("`", "'")
    return s


def letters(s: str) -> str:
    return "".join(c for c in s if c.isalpha())


def upper_ratio(s: str) -> float:
    L = letters(s)
    if not L:
        return 0.0
    return sum(c.isupper() for c in L) / len(L)


def price_value_from_line(text: str):
    t = norm(text).strip(" .|-–—•*·…_")
    m = re.match(r"\+?\s*(\d{1,2}[\s.,]\d{3}|\d{3,5})", t)
    if not m:
        return None
    return parse_price_value(m.group(1))


def parse_price_value(raw: str):
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    v = int(digits)
    if v < 100 or v > 90000:
        return None
    return v


def is_price_only(text: str) -> bool:
    t = norm(text).strip(" .|-–—•")
    if not PRICE_ONLY_RE.match(t):
        return False
    m = re.match(r"\+?\s*(\d{1,2}[\s.,]\d{3}|\d{3,5})", t)
    if not m:
        return False
    rest = t[m.end():].strip()
    if rest and UNIT_AFTER.match(rest):
        return False
    return parse_price_value(m.group(1)) is not None


def find_prices(text: str):
    """Return (prices, text_without_prices)."""
    t = norm(text)
    # drop leader dots
    spans = []
    prices = []
    for m in PRICE_FIND_RE.finditer(t):
        after = t[m.end(): m.end() + 4]
        # reject quantities like 130g, 12 pcs, 11h
        tail = t[m.end():]
        if UNIT_AFTER.match(tail.lstrip()):
            continue
        # reject if glued to letters before (e.g. H45) already handled by (?<!\d)
        before = t[: m.start()]
        if re.search(r"[A-Za-z]$", before) and re.match(r"\d{3,5}$", m.group(1)) and not re.search(r"[\s.,]", m.group(1)):
            # "ROLL5000" unlikely; "BURGER 4500" has space so before ends with space not letter
            pass
        val = parse_price_value(m.group(1))
        if val is None:
            continue
        # avoid matching the first group of a phone inside the line
        window = t[max(0, m.start() - 3): m.end() + 12]
        if PHONE_RE.search(t) and not re.search(r"FCFA|CFA|\bF\b", t[m.end(): m.end() + 6], re.I):
            # if the line is mostly a phone, skip
            if len(re.findall(r"\d", t)) > 8:
                continue
        prices.append(val)
        spans.append(m.span())
    if not spans:
        return [], clean_name(t)
    # remove price spans from the end preferentially, keep internal numbers that are quantities
    # If a price sits before the last third, it may be a quantity. Keep prices that are
    # near the end or preceded by space/dot.
    kept = []
    kept_spans = []
    for val, (a, b) in zip(prices, spans):
        prefix = t[max(0, a - 3):a]
        near_end = b >= len(t) - 8 or (len(t) - b) < 10
        if near_end or re.search(r"[\s.•·…\-–]", prefix):
            kept.append(val)
            kept_spans.append((a, b))
    if not kept:
        return [], clean_name(t)
    # cut from the first kept price that is in the last 40% or after a leader
    cut = kept_spans[0][0]
    for (a, b) in kept_spans:
        if a > len(t) * 0.35:
            cut = a
            break
    name = t[:cut]
    return kept, clean_name(name)


def clean_name(s: str) -> str:
    s = norm(s)
    s = re.sub(r"[.*•·…_=]{2,}", " ", s)
    s = re.sub(r"^[\s•\-\–\—\*\|.=_]+", "", s)
    s = re.sub(r"[\s.\-–—•·…\*\|=_]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    s = re.sub(r"^(NOUVEAU|NEW)\s+", "", s, flags=re.I)
    return s


def clean_comp(parts):
    out = []
    for c in parts:
        c = clean_name(c)
        if not c or is_noise(c):
            continue
        if out and out[-1].lower() == c.lower():
            continue
        out.append(c)
    text = ", ".join(out)
    text = re.sub(r",\s*,", ", ", text)
    text = re.sub(r"\s+,", ",", text)
    return text.strip(" ,")


def is_noise(text: str) -> bool:
    t = clean_name(text)
    if not t:
        return True
    low = t.lower()
    if low in SKIP_EXACT:
        return True
    if re.fullmatch(r"\d{1,2}", t):
        return True
    if PHONE_RE.search(t) and upper_ratio(t) < 0.5:
        return True
    if re.search(r"(www\.|https?://|@|gmail|hotmail|\.com\b|\.sn\b)", low):
        return True
    if re.search(r"\b(ouvert|horaires|livraison|tous les jours|jours feries|jours fériés|adresse|facebook|instagram|whatsapp|tiktok)\b", low):
        return True
    if re.search(r"\b(rue|avenue|boulevard|corniche|route)\b", low) and re.search(r"\b(dakar|ngor|almadies|plateau|senegal|sénégal)\b", low):
        return True
    if re.fullmatch(r"[\d\s+./()-]{6,}", t):
        return True
    return False


def mostly_upper(text: str) -> bool:
    return upper_ratio(text) >= 0.82 and len(letters(text)) >= 3


def looks_like_sentence(text: str) -> bool:
    if "," in text or ";" in text:
        return True
    words = text.split()
    if len(words) >= 6:
        return True
    if text[:1].islower():
        return True
    return False


def format_prices(prices, labels=None):
    if not prices:
        return ""
    def fmt(v):
        return f"{v:,}".replace(",", " ")
    if labels and len(labels) == len(prices):
        return " / ".join(f"{fmt(v)} ({lb.lower()})" for v, lb in zip(prices, labels))
    # unique preserve order
    out = []
    for v in prices:
        if v not in out:
            out.append(v)
    return " / ".join(fmt(v) for v in out)


def cluster_columns(text_lines, gap=58):
    body = [L for L in text_lines if 150 < L["y"] < 825]
    if not body:
        return []
    pts = sorted(body, key=lambda L: L["x"])
    groups = [[pts[0]]]
    for L in pts[1:]:
        if L["x"] - groups[-1][-1]["x"] > gap:
            groups.append([L])
        else:
            groups[-1].append(L)
    # merge tiny clusters into nearest substantial neighbour
    changed = True
    while changed and len(groups) > 1:
        changed = False
        for i, g in enumerate(list(groups)):
            if len(g) >= 5:
                continue
            mx = sum(L["x"] for L in g) / len(g)
            best = None
            bestd = 1e9
            for j, h in enumerate(groups):
                if i == j or len(h) < 5:
                    continue
                hx = sum(L["x"] for L in h) / len(h)
                d = abs(mx - hx)
                if d < bestd:
                    bestd = d
                    best = j
            if best is not None and bestd < 170:
                groups[best].extend(g)
                groups.pop(i)
                changed = True
                break
    groups.sort(key=lambda g: min(L["x"] for L in g))
    return groups


def attach_prices_global(text_lines, price_lines, max_dx=260):
    """Attach a price to the text line just above it, on its left.

    Descriptions sit under the title, so a price aligned with the title
    must not be given to the line below it.
    """
    used = set()
    for i, P in enumerate(price_lines):
        cands = []
        for L in text_lines:
            dy = P["y"] - L["y"]  # >0 when the text sits above the price
            if dy < -4 or dy > 20:
                continue
            if L["x"] > P["x"] + 12:
                continue
            if P["x"] - L["x"] > max_dx:
                continue
            cands.append((dy, -L["x"], L))
        if not cands:
            continue
        cands.sort()
        host = cands[0][2]
        dy_host = P["y"] - host["y"]
        # Price printed under the ingredient list belongs to the uppercase title.
        if dy_host > 8 and not mostly_upper(host["t"]):
            titles = [
                L for L in text_lines
                if L["y"] <= host["y"]
                and host["y"] - L["y"] <= 80
                and abs(L["x"] - host["x"]) <= 50
                and mostly_upper(L["t"])
                and len(letters(L["t"])) >= 3
            ]
            if titles:
                host = max(titles, key=lambda L: L["y"])
        host.setdefault("inline_prices", []).append(P)
        used.add(i)
    return [P for i, P in enumerate(price_lines) if i not in used]


def parse_column(lines, page, etab, priced_page=True):
    lines = sorted(lines, key=lambda L: (round(L["y"], 0), L["x"]))
    items = []
    cat = "Carte"
    cur = None
    pending_prices = []

    def flush():
        nonlocal cur
        if not cur:
            return
        nom = clean_name(cur["nom"])
        if nom and not is_noise(nom) and len(letters(nom)) >= 3:
            comp = [c for c in cur["comp"] if clean_name(c).lower() != nom.lower()]
            items.append({
                "etablissement": etab,
                "type": cur["type"],
                "nom": nom,
                "composition": clean_comp(comp),
                "prix": format_prices(cur["prices"], cur["labels"] if cur["labels"] else None),
                "page": page,
            })
        cur = None

    def start(nom, prices, labels=None):
        nonlocal cur, pending_prices
        flush()
        use = list(prices)
        if not use and pending_prices:
            use = list(pending_prices[-1])
            pending_prices = []
        cur = {"nom": nom, "prices": use, "labels": labels or [], "comp": [], "type": cat}

    # Build a simple sequence of events
    events = []
    for L in lines:
        if L.get("kind") == "price":
            val = price_value_from_line(L["t"])
            if val:
                events.append({"kind": "price", "val": val, "y": L["y"], "t": L["t"]})
            continue
        inline = []
        for P in L.get("inline_prices", []):
            v = price_value_from_line(P["t"])
            if v:
                inline.append(v)
        prices, name = find_prices(L["t"])
        for v in inline:
            if v not in prices:
                prices.append(v)
        if is_noise(name) and not prices:
            continue
        if not name and not prices:
            continue
        events.append({"kind": "text", "t": name, "prices": prices, "y": L["y"]})

    for i, ev in enumerate(events):
        if ev["kind"] == "price":
            # Price under a dish that does not have one yet belongs to that dish.
            # A price after a dish that is already priced is kept for the next dish.
            if cur and cur["labels"] and len(cur["prices"]) < len(cur["labels"]):
                cur["prices"].append(ev["val"])
            elif cur and not cur["prices"]:
                cur["prices"].append(ev["val"])
            else:
                pending_prices.append([ev["val"]])
                if len(pending_prices) > 3:
                    pending_prices = pending_prices[-3:]
            continue

        name = ev["t"]
        prices = list(ev["prices"])
        if not name and prices:
            for v in prices:
                if cur and not cur["prices"]:
                    cur["prices"].append(v)
                elif cur and cur["labels"] and len(cur["prices"]) < len(cur["labels"]):
                    cur["prices"].append(v)
                else:
                    pending_prices.append([v])
            continue
        nxt = next((e for e in events[i + 1:] if e["kind"] == "text" and e["t"]), None)

        key = name.upper().strip()
        if key in VARIANT and (prices or cur):
            if cur:
                cur["labels"].append(key)
                cur["prices"].extend(prices)
                continue
            # no current dish: keep as its own item (size-based products)
            start(name, prices)
            continue

        upper = mostly_upper(name) and len(name) <= 46 and not prices
        nxt_lower = bool(nxt) and (nxt["t"][:1].islower() or looks_like_sentence(nxt["t"])) and not nxt["prices"]
        nxt_priced_name = bool(nxt) and (nxt["prices"] or mostly_upper(nxt["t"]) or (nxt["t"][:1].isupper() and not looks_like_sentence(nxt["t"])))

        if upper and not prices and priced_page:
            if nxt_lower:
                start(name, prices)
                continue
            if nxt_priced_name or nxt is None:
                flush()
                cat = name.title() if name.isupper() else name
                pending_prices = []
                continue

        if prices or name:
            if cur and not prices and not cur["prices"] and mostly_upper(cur["nom"]) and mostly_upper(name) and not cur["comp"]:
                # wrapped title ("NOUILLES SAUTÉES AU" / "LÉGUMES"), not two dishes
                tail = cur["nom"].split()[-1].upper() if cur["nom"].split() else ""
                if tail in {"AU", "AUX", "DE", "DES", "DU", "ET", "A", "À", "AND", "WITH", "OF", "THE"} or cur["nom"].endswith("-"):
                    cur["nom"] = clean_name(cur["nom"] + " " + name)
                    continue
            if cur and not prices and looks_like_sentence(name):
                cur["comp"].append(name)
                continue
            if cur and not prices and not mostly_upper(name) and upper_ratio(name) < 0.7:
                cur["comp"].append(name)
                continue
            start(name, prices)
            continue

    flush()
    return items


def parse_page(page, etab):
    raw = load_page(page)
    if not raw:
        return []
    # drop header contact block somewhat, but keep menu titles below ~140
    usable = [L for L in raw if L["y"] < 820 and L["c"] >= 0.35]
    text, prices = [], []
    for L in usable:
        if is_price_only(L["t"]):
            # ignore giant phone-like header prices above menu
            if L["y"] < 145:
                continue
            prices.append(L)
        else:
            if L["y"] < 145 and (PHONE_RE.search(L["t"]) or is_noise(L["t"])):
                continue
            text.append(L)
    columns = cluster_columns(text)
    if not columns:
        columns = [text]
    leftover = attach_prices_global(text, prices)
    col_index = {}
    for i, col in enumerate(columns):
        for L in col:
            col_index[id(L)] = i
    price_buckets = {i: [] for i in range(len(columns))}
    for P in leftover:
        best = None
        best_score = 1e9
        for L in text:
            if id(L) not in col_index:
                continue
            dy = P["y"] - L["y"]
            if dy < -8 or dy > 36:
                continue
            dx = P["x"] - L["x"]
            if dx < -20 or dx > 280:
                continue
            score = abs(dy) * 4 + abs(dx) * 0.2
            if score < best_score:
                best_score = score
                best = L
        if best is None:
            continue
        price_buckets[col_index[id(best)]].append(P)
    items = []
    for i, col in enumerate(columns):
        seq = [dict(L, kind="text") for L in col]
        for P in price_buckets[i]:
            seq.append(dict(P, kind="price"))
        items.extend(parse_column(seq, page, etab, priced_page=len(prices) >= 4))
    return items


def load_manual():
    path = Path("/Users/mac/Kaayfi/monmenu-extraction/manual_menus.py")
    ns = {}
    exec(path.read_text(), ns)
    return ns["MANUAL"]


def postprocess(rows):
    manual = load_manual()
    replaced = set(manual)
    kept = [r for r in rows if r["etablissement"] not in replaced]
    for etab, items in manual.items():
        kept.extend(items)
    junk = {
        "naturalmente italiano", "des saveurs ensoleillees", "des saveurs ensoleillées",
        "scan me", "bon appetit", "sahten", "bel bel", "yay", "foodly",
        "produits secs, frais et surgeles", "produits secs, frais et surgelés",
    }
    cleaned = []
    seen = set()
    for r in kept:
        nom = clean_name(r["nom"])
        if not nom or len(letters(nom)) < 3:
            continue
        if nom.lower() in junk:
            continue
        if nom.upper() in VARIANT | {"FCFA", "CFA", "SOLO DUO", "SOLO", "DUO"}:
            continue
        if r["etablissement"] == "La Duchesse" and r["type"].lower().startswith("pizza") and not r["prix"]:
            r = dict(r)
            r["prix"] = "3 000 (pm) / 4 000 (mm) / 5 000 (gm)"
        r = dict(r)
        r["nom"] = nom
        r["composition"] = clean_comp(r["composition"].split(", ")) if r["composition"] else ""
        key = (r["etablissement"], r["type"], r["nom"].lower(), r["prix"], r.get("page", ""))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(r)
    return cleaned


def main():
    rows = []
    for etab, pages in PLACES:
        for p in pages:
            rows.extend(parse_page(p, etab))
    cleaned = postprocess(rows)

    fields = ["etablissement", "type", "nom", "composition", "prix", "page"]
    for csv_path in (OUT / "monmenu2025_mets.csv", Path("/Users/mac/Kaayfi/monmenu2025_mets.csv")):
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(cleaned)

    # summary
    from collections import Counter
    c = Counter(r["etablissement"] for r in cleaned)
    print(f"TOTAL {len(cleaned)}")
    for etab, _ in PLACES:
        print(f"{c.get(etab,0):4d}  {etab}")
    print("WROTE", csv_path)


if __name__ == "__main__":
    main()
