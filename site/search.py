"""Recherche de mets : accents, préfixes, synonymes, budget, lieu."""
from __future__ import annotations

import math
import re
import sqlite3
from datetime import datetime

from catalogue import DB_PATH, connect, fold, squash

# Chaque groupe est interchangeable dans la requête.
GROUPS = [
    ["burger", "hamburger"],
    ["poulet", "chicken", "volaille"],
    ["boeuf", "beef"],
    ["crevette", "crevettes", "gambas"],
    ["saumon", "salmon"],
    ["thon", "tuna"],
    ["pizza", "pizzas"],
    ["sushi", "maki"],
    ["salade", "salades"],
    ["cafe", "coffee"],
    ["chocolat", "chocolate"],
    ["poisson", "fish"],
    ["vegetarien", "veggie"],
    ["chawarma", "shawarma"],
    ["frite", "frites"],
    ["glace", "gelato"],
    ["pate", "pates", "pasta"],
    ["riz", "rice"],
    ["taco", "tacos"],
    ["dessert", "gateau"],
    ["brunch", "dejeuner"],
]

PHRASES = [
    ("petit dejeuner", "brunch"),
    ("petit dej", "brunch"),
    ("petit-dejeuner", "brunch"),
    ("ice cream", "glace"),
]

STOP = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "au", "aux",
    "a", "en", "pour", "avec", "sur", "dans", "mon", "ma", "mes", "d", "l",
    "chez", "resto", "restaurant",
}

SYNONYM = {}
for group in GROUPS:
    for word in group:
        SYNONYM[word] = group

PRICE_RE = re.compile(
    r"(?:moins\s+de|maximum|max|jusqu.?a|under|<)\s*(\d[\d\s]{2,7})",
    re.I,
)


def _tokens(text: str) -> list[str]:
    folded = fold(text)
    for source, target in PHRASES:
        folded = folded.replace(source, " " + target + " ")
    words = re.findall(r"[a-z0-9]+", folded)
    return [word for word in words if word not in STOP and len(word) >= 2]


def _expand(token: str) -> list[str]:
    return SYNONYM.get(token, [token])


def _match_expr(tokens: list[str]) -> str:
    parts = []
    for token in tokens:
        alts = []
        for word in _expand(token):
            safe = re.sub(r"[^a-z0-9]", "", word)
            if len(safe) < 2:
                continue
            alts.append(f'"{safe}"')
            if len(safe) >= 3:
                alts.append(safe + "*")
        if alts:
            parts.append("(" + " OR ".join(alts) + ")")
    return " AND ".join(parts)


def _establishments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, nom FROM etablissement ORDER BY length(nom) DESC").fetchall()


def _detect_place(conn: sqlite3.Connection, query: str, tokens: list[str]):
    folded = fold(query)
    squashed = squash(query)
    places = _establishments(conn)
    for place in places:
        if fold(place["nom"]) and fold(place["nom"]) in folded:
            return place
    prefix_hits = []
    for place in places:
        key = squash(place["nom"])
        if len(key) < 5:
            continue
        if squashed == key or (len(squashed) >= 5 and key.startswith(squashed)):
            prefix_hits.append(place)
            continue
        for token in tokens:
            if len(token) >= 5 and key.startswith(token):
                prefix_hits.append(place)
                break
    unique = {place["id"]: place for place in prefix_hits}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def _strip_place(query: str, name: str) -> str:
    folded_name = fold(name)
    folded = fold(query)
    if folded_name in folded:
        folded = folded.replace(folded_name, " ")
    else:
        for token in _tokens(name):
            if len(token) >= 4:
                folded = re.sub(rf"\b{re.escape(token)}\b", " ", folded)
    return folded


def _price_intent(query: str) -> tuple[str, int | None]:
    folded = fold(query)
    match = PRICE_RE.search(folded)
    if not match:
        return query, None
    value = int(re.sub(r"\D", "", match.group(1)))
    cleaned = folded[: match.start()] + " " + folded[match.end() :]
    return cleaned, value


# Lieux imprimés, du plus précis au plus court. Sert uniquement à nommer une adresse.
_LOCAUX = (
    "Pointe des Almadies",
    "Corniche Ouest",
    "Cité Keur Gorgui",
    "Sacré-Cœur",
    "Centre-ville",
    "Dakar-Plateau",
    "Dakar Plateau",
    "Rufisque Ouest",
    "Sicap Baobabs",
    "Amitié 3",
    "Point E",
    "Almadies",
    "Ngaparou",
    "Diamniadio",
    "Mariste",
    "Parcelles",
    "Bourguiba",
    "Médina",
    "Ngor",
    "Yoff",
    "Saly",
)
_VOIE = ("rue ", "avenue ", "boulevard ", "bd ", "route ", "allee ", "impasse ", "voie ", "esplanade ", "rond-point")


def lieu_court(adresse: str) -> str:
    """Quartier ou voie réellement écrit dans l'adresse. Vide si ce n'est pas un lieu."""
    folded = fold(adresse)
    if not folded or folded.startswith("non imprim") or folded.startswith("renseignement"):
        return ""
    found = []
    streets = []
    for part in (adresse or "").split(","):
        label = re.sub(r"\s*\([^)]*\)", "", part).strip(" .")
        key = fold(label)
        if len(key) < 3 or key in {"dakar", "senegal"} or key[:1].isdigit():
            continue
        best = ""
        for lieu in _LOCAUX:
            if fold(lieu) in key and len(lieu) > len(best):
                best = lieu
        if best:
            found.append((any(key.startswith(prefix) for prefix in _VOIE), best))
            continue
        if any(key.startswith(prefix) for prefix in _VOIE):
            if label[:1].islower():
                label = label[:1].upper() + label[1:]
            streets.append(re.sub(r"\s+", " ", label).strip())
    plain = [label for is_street, label in found if not is_street]
    if plain:
        return plain[0]
    if found:
        return found[0][1]
    return streets[0] if streets else ""


def _sites(conn: sqlite3.Connection, etab_id: int, brand: str = "") -> list[dict]:
    if not brand:
        row = conn.execute("SELECT nom FROM etablissement WHERE id = ?", (etab_id,)).fetchone()
        brand = row["nom"] if row else ""
    sites = []
    rows = conn.execute(
        "SELECT * FROM site WHERE etablissement_id = ? ORDER BY ordre",
        (etab_id,),
    ).fetchall()
    for site in rows:
        phones = conn.execute(
            "SELECT affichage, e164 FROM telephone WHERE site_id = ? ORDER BY id",
            (site["id"],),
        ).fetchall()
        label = lieu_court(site["adresse"])
        sites.append({
            "id": site["id"],
            "adresse": site["adresse"],
            "horaires": site["horaires"],
            "lieu": label,
            "nom": brand,
            "telephones": [{"affichage": p["affichage"], "e164": p["e164"]} for p in phones],
        })
    labels = [site["lieu"] for site in sites if site["lieu"]]
    if len(labels) > 1:
        sites = [site for site in sites if site["lieu"]]
        for site in sites:
            site["nom"] = f"{brand} {site['lieu']}"
    return sites


def _filter_sites(sites: list[dict], ou: str = "", only: str = "") -> list[dict]:
    chosen = list(sites)
    if only:
        wanted = fold(only)
        chosen = [site for site in chosen if fold(site["nom"]) == wanted]
    needle = fold(ou)
    if needle:
        chosen = [site for site in chosen if needle in fold(site.get("adresse") or "")]
    return chosen


def _lieu(conn: sqlite3.Connection, place) -> dict:
    row = conn.execute("SELECT logo FROM etablissement WHERE id = ?", (place["id"],)).fetchone()
    return {
        "id": place["id"],
        "nom": place["nom"],
        "logo": (row["logo"] or "") if row else "",
        "sites": _sites(conn, place["id"]),
    }


def _plat(row, nom: str, sites: list, logo: str) -> dict:
    return {
        "id": row["id"],
        "nom": row["nom"],
        "composition": row["composition"],
        "type": row["type"],
        "prix": row["prix_texte"],
        "page": row["page"],
        "image": row["image"] or "",
        "logo": logo or "",
        "etablissement": nom,
        "sites": sites,
    }


# Libellés de cuisine de l'accueil, traduits en plats réellement au catalogue.
CUISINE = {
    "senegalaise": '("yassa"* OR "thieb"* OR "thiebu"* OR "tiep"* OR "mafe"*)',
}


def _money_bounds(conn, etab_id: int) -> tuple:
    prices = [
        row[0]
        for row in conn.execute(
            """SELECT prix_min FROM met
               WHERE etablissement_id = ? AND prix_min BETWEEN 1000 AND 80000
               ORDER BY prix_min""",
            (etab_id,),
        )
    ]
    if not prices:
        return None, None
    if len(prices) < 8:
        return prices[0], prices[-1]
    start = len(prices) // 10
    return prices[start], prices[-1 - start]


def _expand_cartes(conn, etab_id: int, brand: str, logo: str, total: int, dishes, ou: str = "", only: str = "") -> list[dict]:
    """Une carte par adresse quand l'établissement en a plusieurs."""
    sites = _filter_sites(_sites(conn, etab_id, brand), ou, only)
    if not sites:
        return []
    lo, hi = _money_bounds(conn, etab_id)
    cartes = []
    for site in sites:
        nom = site["nom"]
        cartes.append({
            "nom": nom,
            "logo": logo or "",
            "total": total,
            "prix_min": lo,
            "prix_max": hi,
            "sites": [site],
            "plats": [_plat(dish, nom, [], logo or "") for dish in dishes],
        })
    return cartes


def _cartes_fts(conn, sql_where: str, params: list, ou: str = "", only: str = "", needle: str = "", limit_rest: int = 8):
    groups = conn.execute(
        f"""SELECT e.id, e.nom, e.logo, COUNT(*) AS n
            FROM met_fts
            JOIN met m ON m.id = met_fts.met_id
            JOIN etablissement e ON e.id = m.etablissement_id
            WHERE {sql_where}
            GROUP BY e.id
            ORDER BY n DESC
            LIMIT 24""",
        params,
    ).fetchall()
    ranked = []
    for group in groups:
        dishes = conn.execute(
            f"""SELECT m.*, bm25(met_fts, 8.0, 2.0, 3.0, 5.0, 2.0) AS score
                FROM met_fts
                JOIN met m ON m.id = met_fts.met_id
                WHERE {sql_where} AND m.etablissement_id = ?
                ORDER BY
                  CASE
                    WHEN lower(m.nom) = ? THEN 0
                    WHEN instr(lower(m.nom), ?) > 0 THEN 1
                    ELSE 2
                  END,
                  (m.image != '') DESC,
                  score
                LIMIT 8""",
            [*params, group["id"], needle, needle],
        ).fetchall()
        best = dishes[0]["score"] if dishes else 0
        ranked.append((best, -group["n"], group, dishes))
    ranked.sort(key=lambda item: (item[0], item[1]))
    cartes = []
    for _, _, group, dishes in ranked[:limit_rest]:
        cartes.extend(_expand_cartes(
            conn, group["id"], group["nom"], group["logo"] or "", group["n"], dishes, ou, only,
        ))
    ids = [
        row[0]
        for row in conn.execute(
            f"""SELECT DISTINCT m.etablissement_id
                FROM met_fts JOIN met m ON m.id = met_fts.met_id
                WHERE {sql_where}""",
            params,
        )
    ]
    count = 0
    for eid in ids:
        brand = conn.execute("SELECT nom FROM etablissement WHERE id = ?", (eid,)).fetchone()
        count += len(_filter_sites(_sites(conn, eid, brand["nom"] if brand else ""), ou, only))
    return cartes[:16], count


def _ou_ids(conn, ou: str) -> set:
    needle = fold(ou)
    found = set()
    for row in conn.execute("SELECT etablissement_id, adresse FROM site"):
        if needle and needle in fold(row["adresse"]):
            found.add(row["etablissement_id"])
    return found


def _restrict(where: list, params: list, ou_ids) -> None:
    if not ou_ids:
        return
    where.append(f"m.etablissement_id IN ({','.join('?' * len(ou_ids))})")
    params.extend(sorted(ou_ids))


def _detect_lieu(conn, query: str):
    """Nom d'adresse le plus long contenu dans la requête, ex. O'Sushi Bar Saly."""
    folded = fold(query)
    best = None
    best_len = 0
    for row in conn.execute("SELECT id, nom FROM etablissement"):
        sites = _sites(conn, row["id"], row["nom"])
        if len([site for site in sites if site["lieu"]]) < 2:
            continue
        for site in sites:
            key = fold(site["nom"])
            if key in folded and len(key) > best_len:
                best = (row, site)
                best_len = len(key)
    return best


def search(query: str, prix_max: int | None = None, plancher: int | None = None, ou: str | None = None, limit: int = 24, path=DB_PATH) -> dict:
    conn = connect(path)
    try:
        text, parsed_max = _price_intent(query or "")
        if prix_max is None:
            prix_max = parsed_max
        cuisine = CUISINE.get(fold(text).strip())
        only = ""
        if cuisine:
            place = None
            tokens = []
            expr = cuisine
        else:
            hit = _detect_lieu(conn, text)
            if hit:
                place = hit[0]
                only = hit[1]["nom"]
                dish_text = _strip_place(text, only)
            else:
                place = _detect_place(conn, text, _tokens(text))
                dish_text = _strip_place(text, place["nom"]) if place else text
            tokens = _tokens(dish_text)
            expr = _match_expr(tokens)
        if not expr and tokens:
            # faute probable : on relâche la dernière lettre
            softer = [token[:-1] if len(token) >= 5 else token for token in tokens]
            expr = _match_expr(softer)

        ou_ids = _ou_ids(conn, ou) if ou and ou.strip() else None
        if ou_ids is not None and not ou_ids:
            return {
                "q": query,
                "ou": ou or "",
                "prix_max": prix_max,
                "prix_min": plancher,
                "etablissement": None,
                "total": 0,
                "restaurants": 0,
                "plats": [],
                "cartes": [],
                "lieu": None,
            }

        plats = []
        total = 0
        if expr:
            where = ["met_fts MATCH ?"]
            params: list = [expr]
            if place:
                where.append("m.etablissement_id = ?")
                params.append(place["id"])
            if prix_max is not None:
                where.append("m.prix_min IS NOT NULL AND m.prix_min <= ?")
                params.append(prix_max)
            if plancher is not None:
                where.append("m.prix_min IS NOT NULL AND m.prix_min >= ?")
                params.append(plancher)
            _restrict(where, params, ou_ids)
            sql_where = " AND ".join(where)
            total = conn.execute(
                f"""SELECT COUNT(*) FROM met_fts
                    JOIN met m ON m.id = met_fts.met_id
                    WHERE {sql_where}""",
                params,
            ).fetchone()[0]
            needle = " ".join(tokens)
            rows = conn.execute(
                f"""SELECT m.*, bm25(met_fts, 8.0, 2.0, 3.0, 5.0, 2.0) AS score
                    FROM met_fts
                    JOIN met m ON m.id = met_fts.met_id
                    JOIN etablissement e ON e.id = m.etablissement_id
                    WHERE {sql_where}
                    ORDER BY
                      CASE
                        WHEN lower(m.nom) = ? THEN 0
                        WHEN instr(lower(m.nom), ?) > 0 THEN 1
                        ELSE 2
                      END,
                      score
                    LIMIT ?""",
                [*params, needle, needle, limit],
            ).fetchall()
            if not rows and tokens:
                softer = [token[:-1] if len(token) >= 5 else token for token in tokens]
                retry = _match_expr(softer)
                if retry and retry != expr:
                    params[0] = retry
                    rows = conn.execute(
                        f"""SELECT m.*, bm25(met_fts, 8.0, 2.0, 3.0, 5.0, 2.0) AS score
                            FROM met_fts JOIN met m ON m.id = met_fts.met_id
                            JOIN etablissement e ON e.id = m.etablissement_id
                            WHERE {sql_where}
                            ORDER BY score LIMIT ?""",
                        [*params, limit],
                    ).fetchall()
                    total = len(rows)
            site_cache: dict[int, list] = {}
            brand_cache: dict[int, tuple] = {}
            for row in rows:
                eid = row["etablissement_id"]
                if eid not in site_cache:
                    site_cache[eid] = _sites(conn, eid)
                if eid not in brand_cache:
                    etab = conn.execute("SELECT nom, logo FROM etablissement WHERE id = ?", (eid,)).fetchone()
                    brand_cache[eid] = (etab["nom"], etab["logo"] or "")
                nom, logo = brand_cache[eid]
                plats.append(_plat(row, nom, site_cache[eid], logo))
        elif place:
            if ou_ids is not None and place["id"] not in ou_ids:
                rows = []
                total = 0
                cartes = []
                restaurant_count = 0
            else:
                rows = conn.execute(
                    """SELECT * FROM met WHERE etablissement_id = ?
                       ORDER BY page, id LIMIT ?""",
                    (place["id"], limit),
                ).fetchall()
                total = conn.execute(
                    "SELECT COUNT(*) FROM met WHERE etablissement_id = ?",
                    (place["id"],),
                ).fetchone()[0]
                brand = conn.execute("SELECT logo FROM etablissement WHERE id = ?", (place["id"],)).fetchone()
                logo = (brand["logo"] or "") if brand else ""
                sites = _filter_sites(_sites(conn, place["id"], place["nom"]), ou or "", only)
                shown = sites[0]["nom"] if len(sites) == 1 else place["nom"]
                plats = [_plat(row, shown, sites, logo) for row in rows]
                preview = rows[:8]
                cartes = _expand_cartes(conn, place["id"], place["nom"], logo, total, preview, ou or "", only) if rows else []
                restaurant_count = len(cartes)
        elif prix_max is not None or plancher is not None or ou_ids is not None:
            where = ["1 = 1"]
            params = []
            if prix_max is not None or plancher is not None:
                where.append("m.prix_min IS NOT NULL")
            if prix_max is not None:
                where.append("m.prix_min <= ?")
                params.append(prix_max)
            if plancher is not None:
                where.append("m.prix_min >= ?")
                params.append(plancher)
            _restrict(where, params, ou_ids)
            sql_where = " AND ".join(where)
            total = conn.execute(f"SELECT COUNT(*) FROM met m WHERE {sql_where}", params).fetchone()[0]
            rows = conn.execute(
                f"""SELECT m.* FROM met m
                    WHERE {sql_where}
                    ORDER BY (m.image != '') DESC, m.prix_min, m.id
                    LIMIT ?""",
                [*params, limit],
            ).fetchall()
            site_cache = {}
            brand_cache = {}
            for row in rows:
                eid = row["etablissement_id"]
                if eid not in site_cache:
                    site_cache[eid] = _sites(conn, eid)
                if eid not in brand_cache:
                    etab = conn.execute(
                        "SELECT nom, logo FROM etablissement WHERE id = ?", (eid,)
                    ).fetchone()
                    brand_cache[eid] = (etab["nom"], etab["logo"] or "")
                nom, logo = brand_cache[eid]
                plats.append(_plat(row, nom, site_cache[eid], logo))
            groups = conn.execute(
                f"""SELECT e.id, e.nom, e.logo, COUNT(*) AS n,
                           MIN(m.prix_min) AS lo, MAX(m.prix_min) AS hi
                    FROM met m JOIN etablissement e ON e.id = m.etablissement_id
                    WHERE {sql_where}
                    GROUP BY e.id
                    ORDER BY n DESC
                    LIMIT 8""",
                params,
            ).fetchall()
            cartes = []
            for group in groups:
                dishes = conn.execute(
                    f"""SELECT * FROM met m
                        WHERE etablissement_id = ? AND {sql_where}
                        ORDER BY (image != '') DESC, prix_min, id
                        LIMIT 8""",
                    [group["id"], *params],
                ).fetchall()
                cartes.extend(_expand_cartes(
                    conn, group["id"], group["nom"], group["logo"] or "", group["n"], dishes, ou or "", only,
                ))
            ids = [
                row[0]
                for row in conn.execute(
                    f"SELECT DISTINCT etablissement_id FROM met m WHERE {sql_where}",
                    params,
                )
            ]
            restaurant_count = 0
            for eid in ids:
                brand = conn.execute("SELECT nom FROM etablissement WHERE id = ?", (eid,)).fetchone()
                restaurant_count += len(_filter_sites(_sites(conn, eid, brand["nom"] if brand else ""), ou or "", only))
            cartes = cartes[:16]
        else:
            cartes = []
            restaurant_count = 0

        if expr:
            cartes, restaurant_count = _cartes_fts(
                conn, sql_where, params, ou or "", only, needle.lower(),
            )

        return {
            "q": query,
            "ou": ou or "",
            "prix_max": prix_max,
            "prix_min": plancher,
            "etablissement": place["nom"] if place else None,
            "total": total,
            "restaurants": restaurant_count,
            "plats": plats,
            "cartes": cartes,
            "lieu": _lieu(conn, place) if place and not plats else None,
        }
    finally:
        conn.close()


# Centroïdes publics, uniquement pour choisir un libellé d'adresse imprimé.
# La distance n'est jamais affichée.
QUARTIERS = (
    ("Almadies", 14.7455, -17.5160),
    ("Ngor", 14.7488, -17.5055),
    ("Ouakam", 14.7235, -17.4905),
    ("Yoff", 14.7610, -17.4785),
    ("Point E", 14.6938, -17.4592),
    ("Cité Keur Gorgui", 14.7162, -17.4672),
    ("Corniche Ouest", 14.6932, -17.4728),
    ("Médina", 14.6802, -17.4458),
    ("Centre-ville", 14.6698, -17.4315),
    ("Sicap Baobabs", 14.7065, -17.4555),
    ("Amitié 3", 14.7115, -17.4575),
    ("Mariste", 14.7395, -17.4315),
    ("Parcelles", 14.7645, -17.4385),
    ("Saly", 14.4425, -17.0125),
    ("Ngaparou", 14.4615, -17.0720),
    ("Rufisque Ouest", 14.7180, -17.2780),
    ("Diamniadio", 14.7220, -17.1850),
)
_LIEU_MAX_KM = 30

_MOMENT_SQL = {
    "matin": (
        """(lower(m.type) LIKE '%petit%' OR lower(m.type) LIKE '%brunch%'
            OR lower(m.type) LIKE '%matin%' OR lower(m.type) LIKE '%viennois%')
           AND lower(m.type) NOT LIKE '%four%'""",
        """CASE WHEN lower(m.type) LIKE '%petit%' OR lower(m.type) LIKE '%brunch%'
                  OR lower(m.type) LIKE '%matin%' THEN 0 ELSE 1 END""",
    ),
    "midi": (
        """(lower(m.type) LIKE '%plat%' OR lower(m.type) LIKE '%burger%'
            OR lower(m.type) LIKE '%sandwich%' OR lower(m.type) LIKE '%pizza%'
            OR lower(m.type) LIKE '%club%' OR lower(m.type) LIKE '%dwich%'
            OR lower(m.type) LIKE '%bagel%' OR lower(m.type) LIKE '%mini%'
            OR lower(m.type) LIKE '%tartine%')
           AND lower(m.type) NOT LIKE '%crepe%' AND lower(m.type) NOT LIKE '%crêpe%'
           AND lower(m.nom) NOT LIKE '%boisson%'""",
        """CASE WHEN lower(m.type) LIKE '%sandwich%' OR lower(m.type) LIKE '%club%'
                  OR lower(m.type) LIKE '%dwich%' OR lower(m.type) LIKE '%bagel%'
                  OR lower(m.type) LIKE '%plat%' THEN 0 ELSE 1 END""",
    ),
    "apres": (
        """(lower(m.type) LIKE '%dessert%' OR lower(m.type) LIKE '%crêpe%'
            OR lower(m.type) LIKE '%crepe%' OR lower(m.type) LIKE '%viennois%'
            OR lower(m.type) LIKE '%café%' OR lower(m.type) LIKE '%cafe%')
           AND lower(m.type) NOT LIKE '%pizza%'""",
        "0+0",
    ),
    "soir": (
        """(lower(m.type) LIKE '%plat%' OR lower(m.type) LIKE '%grill%'
            OR lower(m.type) LIKE '%pizza%' OR lower(m.type) LIKE '%sushi%'
            OR lower(m.type) LIKE '%burger%' OR lower(m.type) LIKE '%bowl%'
            OR lower(m.type) LIKE '%salade%'
            OR lower(m.type) LIKE '%quinoa%' OR lower(m.type) LIKE '%soupe%'
            OR lower(m.type) LIKE '%mini%')
           AND lower(m.type) NOT LIKE '%crepe%' AND lower(m.type) NOT LIKE '%crêpe%'
           AND lower(m.nom) NOT LIKE '%boisson%'""",
        """CASE WHEN lower(m.type) LIKE '%bowl%' OR lower(m.type) LIKE '%salade%'
                  OR lower(m.type) LIKE '%quinoa%' THEN 0
                 WHEN lower(m.type) LIKE '%mini%' OR lower(m.type) LIKE '%grill%' THEN 1
                 ELSE 2 END""",
    ),
}


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def lieu_proche(lat: float, lng: float) -> str:
    """Quartier du catalogue le plus proche, ou une chaîne vide si rien n'est proche."""
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return ""
    best = ""
    best_km = _LIEU_MAX_KM
    for label, qlat, qlng in QUARTIERS:
        km = _km(lat, lng, qlat, qlng)
        if km < best_km:
            best_km = km
            best = label
    return best


def moment_du_jour(heure: int | None) -> str:
    if heure is None:
        heure = datetime.now().hour
    if 5 <= heure <= 10:
        return "matin"
    if 11 <= heure <= 14:
        return "midi"
    if 15 <= heure <= 17:
        return "apres"
    if 18 <= heure <= 22:
        return "soir"
    return "nuit"


def _nearby(conn, needle: str) -> list[dict]:
    key = fold(needle)
    rows = conn.execute(
        """SELECT e.id, e.nom, e.logo, COUNT(m.id) AS n
           FROM etablissement e
           JOIN met m ON m.etablissement_id = e.id
           GROUP BY e.id
           ORDER BY n DESC"""
    ).fetchall()
    pres = []
    for place in rows:
        sites = _sites(conn, place["id"])
        local = next((site for site in sites if key in fold(site["adresse"])), None)
        if not local:
            continue
        lo, hi = _money_bounds(conn, place["id"])
        cover = conn.execute(
            "SELECT image FROM met WHERE etablissement_id = ? AND image != '' LIMIT 1",
            (place["id"],),
        ).fetchone()
        pres.append({
            "nom": local["nom"],
            "logo": place["logo"] or "",
            "cover": (cover["image"] if cover else "") or "",
            "adresse": local["adresse"],
            "horaires": local["horaires"],
            "telephones": local["telephones"],
            "prix_min": lo,
            "prix_max": hi,
        })
        if len(pres) == 3:
            break
    return pres


def _du_moment(conn, moment: str) -> list[dict]:
    key = "soir" if moment == "nuit" else moment
    where, rank = _MOMENT_SQL[key]
    rows = conn.execute(
        f"""SELECT m.*, e.nom AS enom, e.logo AS elogo
            FROM met m JOIN etablissement e ON e.id = m.etablissement_id
            WHERE {where}
              AND lower(m.type) NOT LIKE '%boisson%'
              AND lower(m.type) NOT LIKE '%jus%'
              AND lower(m.nom) NOT LIKE '%coca%'
              AND lower(m.nom) NOT LIKE '%sprite%'
              AND lower(m.nom) NOT LIKE '%fanta%'
            ORDER BY
              CASE WHEN m.image != '' THEN 0 ELSE 1 END,
              {rank},
              m.prix_min, m.id
            LIMIT 4"""
    ).fetchall()
    cache: dict[int, list] = {}
    plats = []
    for row in rows:
        eid = row["etablissement_id"]
        if eid not in cache:
            cache[eid] = _sites(conn, eid)
        plats.append(_plat(row, row["enom"], cache[eid], row["elogo"] or ""))
    return plats


def home(ou: str | None = None, heure: int | None = None, path=DB_PATH) -> dict:
    """Repas du moment, établissements d'un quartier imprimé, plats peu chers photographiés."""
    conn = connect(path)
    try:
        moment = moment_du_jour(heure)
        needle = (ou or "").strip()
        pres = _nearby(conn, needle or "almadies")
        rows = conn.execute(
            """SELECT m.*, e.nom AS enom, e.logo AS elogo
               FROM met m JOIN etablissement e ON e.id = m.etablissement_id
               WHERE m.prix_min BETWEEN 2000 AND 3500
                 AND m.image != ''
                 AND lower(m.type) NOT LIKE '%boisson%'
                 AND lower(m.type) NOT LIKE '%jus%'
                 AND lower(m.nom) NOT LIKE '%coca%'
                 AND lower(m.nom) NOT LIKE '%sprite%'
                 AND lower(m.nom) NOT LIKE '%fanta%'
                 AND lower(m.nom) NOT LIKE '%latte%'
                 AND lower(m.nom) NOT LIKE '%cappu%'
                 AND lower(m.nom) NOT LIKE '%thé%'
                 AND lower(m.nom) NOT LIKE '%the %'
                 AND lower(m.nom) NOT LIKE 'jus %'
               ORDER BY
                 CASE
                   WHEN lower(m.type) LIKE '%mini%' OR lower(m.type) LIKE '%burger%'
                     OR lower(m.type) LIKE '%sandwich%' OR lower(m.type) LIKE '%plat%' THEN 0
                   WHEN lower(m.type) LIKE '%dessert%' OR lower(m.type) LIKE '%snack%'
                     OR lower(m.type) LIKE '%biscuit%' OR lower(m.type) LIKE '%cookie%' THEN 2
                   ELSE 1
                 END,
                 m.prix_min, m.id
               LIMIT 3"""
        ).fetchall()
        budget = []
        cache: dict[int, list] = {}
        for row in rows:
            eid = row["etablissement_id"]
            if eid not in cache:
                cache[eid] = _sites(conn, eid)
            budget.append(_plat(row, row["enom"], cache[eid], row["elogo"] or ""))
        return {
            "moment": moment,
            "pres": pres,
            "pres_perso": bool(needle),
            "budget": budget,
            "du_moment": _du_moment(conn, moment),
        }
    finally:
        conn.close()


def _resolve_nom(conn, nom: str):
    wanted = fold(nom or "")
    brand_hit = None
    for row in conn.execute("SELECT id, nom, logo FROM etablissement"):
        sites = _sites(conn, row["id"], row["nom"])
        for site in sites:
            if fold(site["nom"]) == wanted and fold(site["nom"]) != fold(row["nom"]):
                return row, [site], site["nom"]
        if fold(row["nom"]) == wanted:
            brand_hit = (row, sites, row["nom"])
    return brand_hit


def menu(nom: str, path=DB_PATH):
    conn = connect(path)
    try:
        found = _resolve_nom(conn, nom)
        if not found:
            return None
        row, sites, display = found
        rows = conn.execute(
            "SELECT * FROM met WHERE etablissement_id = ? ORDER BY type, page, id",
            (row["id"],),
        ).fetchall()
        logo = row["logo"] or ""
        return {
            "lieu": {
                "id": row["id"],
                "nom": display,
                "logo": logo,
                "sites": sites,
            },
            "plats": [_plat(item, display, sites, logo) for item in rows],
        }
    finally:
        conn.close()


def dish(met_id: int, lieu_nom: str = "", path=DB_PATH):
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM met WHERE id = ?", (met_id,)).fetchone()
        if not row:
            return None
        etab = conn.execute(
            "SELECT nom, logo FROM etablissement WHERE id = ?",
            (row["etablissement_id"],),
        ).fetchone()
        sites = _sites(conn, row["etablissement_id"], etab["nom"])
        nom = etab["nom"]
        if lieu_nom:
            picked = [site for site in sites if fold(site["nom"]) == fold(lieu_nom)]
            if picked:
                sites = picked
                nom = picked[0]["nom"]
        return _plat(row, nom, sites, etab["logo"] or "")
    finally:
        conn.close()


_STREET = ("rue ", "avenue ", "boulevard ", "bd ", "route ", "allee ", "impasse ", "voie ", "rond-point", "esplanade ", "centre commercial", "lot ")


def _clip(text: str, size: int = 52) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= size:
        return text
    return text[: size - 1].rstrip() + "…"


def _lieu_index(conn):
    """Quartiers et adresses réellement imprimés."""
    labels: dict[str, dict] = {}
    addresses = []
    for row in conn.execute(
        """SELECT e.nom AS resto, s.adresse
           FROM site s JOIN etablissement e ON e.id = s.etablissement_id"""
    ):
        adresse = (row["adresse"] or "").strip()
        if not adresse or fold(adresse).startswith("non imprim"):
            continue
        addresses.append((adresse, row["resto"]))
        for part in adresse.split(","):
            label = re.sub(r"\s*\([^)]*\)", "", part).strip(" .")
            key = fold(label)
            if len(key) < 3 or key in {"dakar", "senegal"} or key[:1].isdigit():
                continue
            bucket = labels.setdefault(key, {"texte": label, "restos": set(), "rue": key.startswith(_STREET)})
            bucket["restos"].add(row["resto"])
            if len(label) < len(bucket["texte"]):
                bucket["texte"] = label
    return list(labels.values()), addresses


def suggest(query: str, kind: str = "met", path=DB_PATH) -> dict:
    conn = connect(path)
    try:
        needle = fold(query or "").strip()
        if kind == "lieu":
            return {"suggestions": _suggest_lieu(conn, needle)}
        return {"suggestions": _suggest_met(conn, needle)}
    finally:
        conn.close()


def _suggest_lieu(conn, needle: str) -> list[dict]:
    labels, addresses = _lieu_index(conn)
    if not needle:
        popular = [item for item in labels if not item["rue"]]
        popular.sort(key=lambda item: (-len(item["restos"]), item["texte"]))
        return [
            {"texte": item["texte"], "genre": "lieu", "detail": _compte(len(item["restos"]))}
            for item in popular[:6]
        ]
    hits = []
    for item in labels:
        key = fold(item["texte"])
        if needle not in key:
            continue
        hits.append((0 if key.startswith(needle) else 1, -len(item["restos"]), len(item["texte"]), {
            "texte": item["texte"],
            "genre": "lieu",
            "detail": _compte(len(item["restos"])),
        }))
    if len(needle) >= 4:
        seen = {fold(item[3]["texte"]) for item in hits}
        for adresse, resto in addresses:
            if needle not in fold(adresse) or fold(adresse) in seen:
                continue
            hits.append((2, 0, len(adresse), {
                "texte": adresse,
                "genre": "lieu",
                "detail": resto,
            }))
    hits.sort(key=lambda item: item[:3])
    return [item[3] for item in hits[:8]]


def _compte(n: int) -> str:
    return f"{n} établissement" if n == 1 else f"{n} établissements"


def _suggest_met(conn, needle: str) -> list[dict]:
    if len(re.sub(r"[^a-z0-9]", "", needle)) < 2:
        return []
    suggestions = []
    seen = set()
    for row in conn.execute("SELECT id, nom FROM etablissement ORDER BY nom"):
        sites = _sites(conn, row["id"], row["nom"])
        multi = len([site for site in sites if site["lieu"]]) > 1
        targets = sites if multi else [None]
        for site in targets:
            nom = site["nom"] if site else row["nom"]
            key = fold(nom)
            if needle not in key:
                continue
            address = ""
            pool = [site] if site else sites
            for item in pool:
                if item and not fold(item["adresse"]).startswith("non imprim"):
                    address = _clip(item["adresse"])
                    break
            suggestions.append((0 if key.startswith(needle) else 1, 0, len(nom), {
                "texte": nom,
                "genre": "restaurant",
                "detail": address,
            }))
            seen.add(key)
    tokens = _tokens(needle)
    expr = _match_expr(tokens) if tokens else ""
    dishes = []
    if expr:
        prefix = (tokens[0] if tokens else needle) + "%"
        rows = conn.execute(
            """SELECT m.nom AS nom, e.nom AS resto
               FROM met_fts
               JOIN met m ON m.id = met_fts.met_id
               JOIN etablissement e ON e.id = m.etablissement_id
               WHERE met_fts MATCH ?
               ORDER BY CASE WHEN lower(m.nom) LIKE ? THEN 0 ELSE 1 END, length(m.nom)
               LIMIT 80""",
            (expr, prefix),
        ).fetchall()
        grouped: dict[str, dict] = {}
        for row in rows:
            key = fold(row["nom"])
            if key in seen:
                continue
            bucket = grouped.setdefault(key, {"texte": row["nom"], "restos": []})
            if row["resto"] not in bucket["restos"]:
                bucket["restos"].append(row["resto"])
        for key, bucket in grouped.items():
            restos = bucket["restos"]
            detail = restos[0] if len(restos) == 1 else f"{len(restos)} restaurants"
            rank = 0 if key.startswith(needle) or fold(bucket["texte"]).startswith(needle) else 1
            dishes.append((rank, 1, -len(restos), {
                "texte": bucket["texte"],
                "genre": "plat",
                "detail": detail,
            }))
    suggestions.extend(dishes)
    suggestions.sort(key=lambda item: item[:3])
    unique = []
    taken = set()
    for _, _, _, item in suggestions:
        key = fold(item["texte"])
        if key in taken:
            continue
        taken.add(key)
        unique.append(item)
        if len(unique) == 8:
            break
    return unique
