"""Logos du catalogue et photos des plats quand la carte en ligne en a une."""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from io import BytesIO
from pathlib import Path

from PIL import Image

import fitz

from catalogue import DB_PATH, connect, squash

PDF = Path("/Users/mac/Downloads/monmenu2025.pdf")
STATIC = Path(__file__).resolve().parent / "static"
LOGOS = STATIC / "logos"
PHOTOS = STATIC / "photos"
STAMP = STATIC / ".photos-ready"
UA = {"User-Agent": "Mozilla/5.0"}

# page, clip (x0, y0, x1, y1) en points PDF
CROPS = {
    "Annapurna": (6, (15, 25, 250, 165)),
    "Aroma Gelato": (8, (16, 8, 178, 172)),
    "Bambou": (10, (15, 25, 280, 165)),
    "Be Bey": (12, (15, 25, 220, 185)),
    "Billy's": (16, (10, 15, 280, 165)),
    "Brasil Burger": (18, (8, 15, 250, 175)),
    "Brazilian Pizza": (20, (360, 0, 595, 95)),
    "Bro's Burger": (22, (15, 20, 260, 165)),
    "Bro's Kebab": (24, (15, 15, 230, 185)),
    "Burger & Co": (26, (40, 4, 560, 95)),
    "Caesar": (28, (18, 12, 195, 175)),
    "Cake House": (32, (40, 8, 270, 120)),
    "Casino Sea Plaza": (34, (15, 20, 210, 185)),
    "Chicken Times": (36, (16, 0, 320, 105)),
    "Chocolate Sarayi": (38, (8, 15, 260, 140)),
    "Ciao Italia": (42, (15, 15, 230, 175)),
    "Coffee Loft": (44, (20, 50, 320, 165)),
    "Elias": (46, (10, 40, 280, 175)),
    "Eric Kayser": (48, (15, 20, 190, 210)),
    "Café Club (FOODLY)": (52, (20, 40, 180, 180)),
    "Pizza di Roma (FOODLY)": (53, (20, 30, 200, 170)),
    "Burger House (FOODLY)": (54, (20, 30, 200, 170)),
    "Shawarma Foodly (FOODLY)": (55, (20, 30, 200, 170)),
    "Gourmandine": (56, (15, 25, 210, 185)),
    "Halo": (58, (310, 28, 575, 125)),
    "Healthy Bar": (60, (25, 0, 290, 185)),
    "Jeff de Bruges": (66, (18, 35, 270, 145)),
    "Kebarma": (68, (205, 168, 385, 282)),
    "L'Epicerie": (70, (0, 0, 280, 190)),
    "L'Orientale": (72, (15, 15, 210, 185)),
    "La Baie d'Along": (74, (15, 15, 230, 185)),
    "La Duchesse": (76, (0, 0, 200, 190)),
    "La Médine": (78, (8, 15, 170, 165)),
    "La Pampa": (80, (10, 16, 210, 125)),
    "La Piazza": (82, (12, 25, 260, 145)),
    "Le Layal": (84, (20, 5, 320, 185)),
    "Le Professeur": (86, (8, 8, 190, 170)),
    "Le Seoul": (88, (15, 15, 260, 165)),
    "Le Taouk": (90, (15, 25, 290, 155)),
    "Mamma Pizza": (92, (14, 38, 245, 130)),
    "Mammy Healthy": (94, (15, 20, 290, 185)),
    "N'ice Cream": (98, (10, 35, 300, 155)),
    "Nomad Foodtruck": (100, (230, 20, 450, 175)),
    "O'Sushi Bar": (102, (10, 15, 210, 165)),
    "O'Wok Bar": (106, (15, 5, 250, 185)),
    "Pink Factory": (108, (10, 10, 340, 130)),
    "Pistache et Noix": (110, (10, 15, 190, 175)),
    "Pizza Papa": (112, (20, 0, 330, 155)),
    "Planet Kebab": (114, (12, 25, 190, 145)),
    "Poz Tacos": (116, (5, 15, 190, 185)),
    "Quick Automatik": (118, (10, 30, 260, 185)),
    "Saveurs d'Asie": (120, (10, 20, 260, 165)),
    "Sen Burger": (122, (10, 15, 210, 185)),
    "Shawarma Express": (124, (10, 15, 290, 165)),
    "So Sushi": (126, (10, 20, 300, 165)),
}


def _slug(text: str) -> str:
    return (squash(text) or "image")[:70]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read().decode("utf-8", "replace")


def _save(url: str, dest: Path) -> bool:
    dest = dest.with_suffix(".jpg")
    if dest.exists() and dest.stat().st_size > 800:
        return True
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        image = Image.open(BytesIO(data)).convert("RGB")
        image.thumbnail((420, 420))
        dest.parent.mkdir(parents=True, exist_ok=True)
        image.save(dest, "JPEG", quality=72, optimize=True)
    except Exception:
        return False
    return dest.exists() and dest.stat().st_size > 800


def render_logos() -> dict[str, str]:
    LOGOS.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    paths = {}
    for name, (page, box) in CROPS.items():
        dest = LOGOS / f"{_slug(name)}.jpg"
        if not dest.exists() or dest.stat().st_size < 800:
            pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(*box), alpha=False)
            pix.save(str(dest))
        paths[name] = f"/logos/{dest.name}"
    doc.close()
    return paths


def _json_array(html: str) -> list:
    marker = html.find("categories_data")
    if marker < 0:
        return []
    start = html.find("[", marker)
    if start < 0:
        return []
    depth = 0
    for index, char in enumerate(html[start:], start):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : index + 1])
                except json.JSONDecodeError:
                    return []
    return []


def _pictures_from_menu(html: str) -> dict[str, str]:
    found = {}
    for category in _json_array(html):
        for product in category.get("products") or []:
            picture = product.get("picture") or ""
            name = product.get("name") or ""
            if name and isinstance(picture, str) and picture.startswith("http"):
                found.setdefault(squash(name), picture)
    return found


def _healthy() -> dict[str, str]:
    html = _fetch("https://dakarfooddelivery.com/restaurant/restaurant-detail/o-healthy-bar")
    found = {}
    for src, alt in re.findall(
        r'src="(https://dakarfooddelivery.com/uploads/menu/[^"]+)"[^>]*alt="([^"]*)"',
        html,
    ):
        if alt.strip():
            found.setdefault(squash(unescape(alt)), src)
    return found


def _chocolate() -> dict[str, str]:
    found = {}
    for page in range(1, 6):
        raw = _fetch(
            "https://chocolatesarayi.sn/wp-json/wc/store/v1/products"
            f"?per_page=100&page={page}"
        )
        products = json.loads(raw)
        if not products:
            break
        for product in products:
            images = product.get("images") or []
            if not images:
                continue
            src = images[0].get("thumbnail") or images[0].get("src") or ""
            name = unescape(product.get("name") or "")
            if name and src.startswith("http"):
                found.setdefault(squash(name), src)
    return found


def collect_photos() -> dict[str, dict[str, str]]:
    """etablissement -> {nom plié -> url}"""
    menus = {
        "Mammy Healthy": "https://mammy-healthy.com",
        "Caesar": "https://caesarlounge.com",
    }
    found = {}
    for name, url in menus.items():
        try:
            pictures = _pictures_from_menu(_fetch(url))
        except Exception as exc:
            print(name, exc)
            pictures = {}
        if pictures:
            found[name] = pictures
            print(f"{name}: {len(pictures)} photos")
    try:
        healthy = _healthy()
        print(f"Healthy Bar: {len(healthy)} photos")
        if healthy:
            found["Healthy Bar"] = healthy
    except Exception as exc:
        print("Healthy Bar", exc)
    try:
        chocolate = _chocolate()
        print(f"Chocolate Sarayi: {len(chocolate)} photos")
        if chocolate:
            found["Chocolate Sarayi"] = chocolate
    except Exception as exc:
        print("Chocolate Sarayi", exc)
    return found


def _ensure_columns(conn) -> None:
    etab_cols = {row[1] for row in conn.execute("PRAGMA table_info(etablissement)")}
    met_cols = {row[1] for row in conn.execute("PRAGMA table_info(met)")}
    if "logo" not in etab_cols:
        conn.execute("ALTER TABLE etablissement ADD COLUMN logo TEXT")
    if "image" not in met_cols:
        conn.execute("ALTER TABLE met ADD COLUMN image TEXT")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(char for char in text if unicodedata.category(char) != "Mn").lower()


# La forme du plat (titre, puis rubrique) gagne sur un ingrédient cité dans la description.
# Ainsi une salade au poulet reste une salade, et des frites d'accompagnement ne remplacent pas le plat.
FORM_RULES = [
    ("pizza", r"pizza|calzone|pepperoni"),
    ("burger", r"burger|hamburger|smash"),
    ("hotdog", r"hot ?dog"),
    ("sandwich", r"sandwich|\bclub\b|bagel|tartine|panini|\bwraps?\b|dwich|manaiche|manakish|fatayer|croque|bagette|baguette"),
    ("poke", r"\bpoke\b"),
    ("salade", r"salade|salad|nicoise|caesar|cesar|\bbowl\b"),
    ("sushi", r"sushi|maki|sashimi|temaki|chirashi|gyoza"),
    ("tacos", r"\btacos\b|quesadilla|burrito"),
    ("pates", r"\bpates\b|pasta|spaghetti|penne|tagliatelle|lasagne|ravioli|risotto|gnocchi|carbonara|bolognaise"),
    ("nouilles", r"nouille|noodle|ramen|pad thai|chow|bo bun|\bpho\b|udon"),
    ("nems", r"\bnems?\b|samoussa|samossa|samosa|rouleaux? de printemps|spring rolls?"),
    ("soupe", r"soupe|veloute|\bsoup\b|potage"),
    ("crepe", r"\bcrepes?\b"),
    ("gaufre", r"gaufre|waffle"),
    ("pancake", r"pancake"),
]

FOOD_RULES = [
    ("thieb", r"thieb|ceeb|tiep|tieboudienn"),
    ("yassa", r"yassa"),
    ("mafe", r"\bmafe\b|domoda|maafe"),
    ("fataya", r"fataya|pastel"),
    ("dibi", r"\bdibi\b"),
    ("brochette", r"brochette"),
    ("shawarma", r"shawarma|chawarma|taouk"),
    ("kebab", r"kebab|doner|gyros"),
    ("wings", r"\bwings?\b|buffalo|\bailes\b"),
    ("tenders", r"tender|nugget|croustillant|crispy (chicken|poulet)"),
    ("frites", r"frites?|\bfries\b"),
    ("poisson", r"poisson|\bfish\b|dorade|thiof|tilapia|saumon|thon|crevette|gambas|shrimp|prawn|calamar|ceviche"),
    ("steak", r"steak|entrecote|bavette|\bboeuf\b"),
    ("poulet", r"poulet|chicken|dinde"),
    ("mezze", r"houmous|hummus|falafel|mezze|taboule"),
    ("omelette", r"omelette"),
    ("cheesecake", r"cheesecake|cheese cake"),
    ("brownie", r"brownie|cookie|fondant au chocolat"),
    ("glace", r"\bglace\b|gelato|sorbet|boule de glace"),
    ("tarte", r"tarte|\bgateau\b|muffin|macaron|eclair|tiramisu|madeleine"),
    ("milkshake", r"milk-?\s?shake|frapp"),
    ("cafe", r"\bcafe\b|coffee|cappu|latte|espresso|expresso|macchiato|chocolat chaud|moccacino|mocaccino"),
    ("the", r"\btea\b|matcha|infusion|(^| )the$|the (vert|noir|menthe|glace|chaud|a la|au )"),
    ("jus", r"\bjus\b|\bsmoothie\b|\bbissap\b|\bbouye\b|\bgingembre\b|\blimonade\b|\blassi\b"),
    ("cocktail", r"(?<!sauce )cocktail|mojito|spritz"),
    ("soda", r"\bsoda\b|coca|fanta|sprite|eau minerale|eau plate|eau gazeuse"),
    ("croissant", r"croissant|viennoiserie|pain au chocolat|brioche"),
    ("petitdej", r"petit dej|brunch|granola|yaourt|muesli"),
    ("pain", r"\bpain\b|baguette"),
]

# Un accompagnement ne doit pas voler l'image quand le plat lui-même est reconnu.
SIDE_KEYS = {"frites", "pain", "soda"}

# Ces mots ne comptent que dans le titre : dans une description ils sont souvent un détail.
TITLE_ONLY = [
    ("glace", r"\bboules?\b"),
    ("tarte", r"\bcake\b"),
]

# Rubrique qui nomme vraiment la famille, quand le titre ne dit rien.
TYPE_ONLY = [
    ("tenders", r"^crispy$"),
    ("frites", r"^frites?$|^fries$"),
]
GENERIC_TYPE = re.compile(
    r"\b(carte|menu|starter|entree|main|course|drink|boisson|formule|suppl|autre|divers|nouveau|avec|servi|accompagnement)\b"
)
SIDE_PHRASE = re.compile(
    r"accompagnee?s? (de |d')?(frites?|salade)|servie?s? avec( des| de| d')? ?(frites?|salade)|\bet des frites\b"
)
# Une pizza est souvent décrite seulement par sa garniture, sans le mot « pizza ».
PIZZA_COMP = re.compile(
    r"(sauce|puree de) tomate.{0,80}(fromage|mozza|emmental|chevre|parmesan)"
    r"|((fromage|mozza|emmental).{0,40}sauce tomate)"
    r"|creme fraiche.{0,90}parmesan"
)
# Ces formes gagnent même si la garniture ressemble à une pizza.
NOT_PIZZA = {"burger", "sandwich", "salade", "poke", "sushi", "tacos", "pates", "nouilles", "nems", "soupe", "crepe", "gaufre", "pancake", "hotdog"}

# Quand le visuel précis n'existe pas, on prend un plat proche déjà photographié.
STUDIO_FALLBACK = {
    "thieb": "plat",
    "yassa": "poulet",
    "mafe": "plat",
    "fataya": "nems",
    "dibi": "brochette",
    "poke": "salade",
    "hotdog": "sandwich",
    "soupe": "plat",
    "cheesecake": "tarte",
    "gaufre": "crepe",
    "milkshake": "jus",
    "the": "cafe",
    "cocktail": "jus",
    "petitdej": "omelette",
    "pain": "croissant",
}


def _compiled(rules):
    return [(key, re.compile(pattern)) for key, pattern in rules]


_FORM = _compiled(FORM_RULES)
_FOOD = _compiled(FOOD_RULES)
_TITLE_ONLY = _compiled(TITLE_ONLY)
_TYPE_ONLY = _compiled(TYPE_ONLY)


def _first_key(text: str, rules, ignore_sides: bool = False) -> str | None:
    hits = [key for key, pattern in rules if pattern.search(text)]
    if ignore_sides:
        strong = [key for key in hits if key not in SIDE_KEYS]
        if strong:
            hits = strong
    return hits[0] if hits else None


def _match_text(text: str, ignore_sides: bool = False) -> str | None:
    if not text.strip():
        return None
    return _first_key(text, _FORM, ignore_sides) or _first_key(text, _FOOD, ignore_sides)


def choose_studio_key(nom: str, type_: str, composition: str) -> str:
    """Le titre prime. Une rubrique claire (Burgers, Pizzas, Salades) passe avant l'ingrédient."""
    title = _fold(nom)
    kind = _fold(type_)
    if kind and not GENERIC_TYPE.search(kind):
        typed = _first_key(kind, _FORM)
        if typed:
            return typed
    named = _first_key(title, _TITLE_ONLY) or _match_text(title)
    composition_text = SIDE_PHRASE.sub(" ", _fold(composition))
    if PIZZA_COMP.search(composition_text) and named not in NOT_PIZZA:
        return "pizza"
    if named:
        return named
    if kind and not GENERIC_TYPE.search(kind):
        typed = _first_key(kind, _TYPE_ONLY)
        if typed:
            return typed
    return _match_text(composition_text, ignore_sides=True) or "plat"


def _studio_file(key: str, available: set[str]) -> str:
    while key not in available and key in STUDIO_FALLBACK:
        key = STUDIO_FALLBACK[key]
    if key not in available:
        key = "plat"
    return f"/photos/studio/{key}.jpg"


def assign_studio(conn) -> int:
    """Donne un visuel fond blanc aux plats qui n'ont pas encore de photo."""
    available = {path.stem for path in (PHOTOS / "studio").glob("*.jpg")}
    if "plat" not in available:
        return 0
    rows = conn.execute(
        """SELECT id, nom, coalesce(type, '') AS type, coalesce(composition, '') AS composition
           FROM met WHERE coalesce(image, '') = ''"""
    ).fetchall()
    for row in rows:
        chosen = choose_studio_key(row["nom"], row["type"], row["composition"])
        conn.execute(
            "UPDATE met SET image = ? WHERE id = ?",
            (_studio_file(chosen, available), row["id"]),
        )
    return len(rows)


def reassign_studio(conn) -> int:
    """Réaligne les photos d'atelier déjà posées sur le titre puis la description."""
    available = {path.stem for path in (PHOTOS / "studio").glob("*.jpg")}
    if "plat" not in available:
        return 0
    rows = conn.execute(
        """SELECT id, nom, coalesce(type, '') AS type, coalesce(composition, '') AS composition, image
           FROM met WHERE image LIKE '/photos/studio/%'"""
    ).fetchall()
    changed = 0
    for row in rows:
        path = _studio_file(choose_studio_key(row["nom"], row["type"], row["composition"]), available)
        if path == row["image"]:
            continue
        conn.execute("UPDATE met SET image = ? WHERE id = ?", (path, row["id"]))
        changed += 1
    return changed


def _relink(conn) -> int:
    linked = 0
    if not PHOTOS.exists():
        return 0
    for folder in PHOTOS.iterdir():
        if not folder.is_dir():
            continue
        rows = conn.execute(
            """SELECT m.id, m.nom, e.nom AS etab FROM met m
               JOIN etablissement e ON e.id = m.etablissement_id"""
        ).fetchall()
        by_file = {_slug(row["nom"]): row for row in rows if _slug(row["etab"]) == folder.name}
        for path in folder.iterdir():
            row = by_file.get(path.stem)
            if not row:
                continue
            public = f"/photos/{folder.name}/{path.name}"
            conn.execute("UPDATE met SET image = ? WHERE id = ?", (public, row["id"]))
            linked += 1
    return linked


def attach(path: Path = DB_PATH) -> dict:
    logos = render_logos()
    conn = connect(path)
    _ensure_columns(conn)
    for name, public in logos.items():
        conn.execute("UPDATE etablissement SET logo = ? WHERE nom = ?", (public, name))

    if STAMP.exists():
        linked = _relink(conn)
        linked += assign_studio(conn)
        linked += reassign_studio(conn)
        conn.commit()
        stats = {
            "logos": conn.execute("SELECT COUNT(*) FROM etablissement WHERE coalesce(logo, '') != ''").fetchone()[0],
            "photos": conn.execute("SELECT COUNT(*) FROM met WHERE coalesce(image, '') != ''").fetchone()[0],
        }
        conn.close()
        print("Images :", stats, "reliées", linked)
        return stats

    photos = collect_photos()
    jobs = []
    linked = 0
    for etab, images in photos.items():
        rows = conn.execute(
            """SELECT m.id, m.nom FROM met m
               JOIN etablissement e ON e.id = m.etablissement_id
               WHERE e.nom = ?""",
            (etab,),
        ).fetchall()
        by_name = {}
        for row in rows:
            by_name.setdefault(squash(row["nom"]), []).append(row)
        for key, url in images.items():
            matches = by_name.get(key)
            if not matches:
                continue
            for row in matches:
                dest = PHOTOS / _slug(etab) / f"{_slug(row['nom'])}.jpg"
                public = f"/photos/{_slug(etab)}/{dest.name}"
                jobs.append((url, dest, row["id"], public))
    def one(job):
        url, dest, met_id, public = job
        if _save(url, dest):
            return met_id, public
        return None

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(one, jobs):
            if not result:
                continue
            met_id, public = result
            conn.execute("UPDATE met SET image = ? WHERE id = ?", (public, met_id))
            linked += 1
            done += 1
    if linked:
        STAMP.write_text(str(linked))
    linked += assign_studio(conn)
    linked += reassign_studio(conn)
    conn.commit()
    stats = {
        "logos": conn.execute("SELECT COUNT(*) FROM etablissement WHERE logo IS NOT NULL AND logo != ''").fetchone()[0],
        "photos": conn.execute("SELECT COUNT(*) FROM met WHERE image IS NOT NULL AND image != ''").fetchone()[0],
    }
    conn.close()
    print("Images :", stats, "téléchargements", linked)
    return stats


if __name__ == "__main__":
    attach()
