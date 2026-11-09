"""Charge le catalogue Mon Menu dans une base SQLite interrogeable."""
from __future__ import annotations

import csv
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METS = ROOT / "monmenu2025_mets.csv"
CONTACTS = ROOT / "monmenu2025_contacts.csv"
DB_PATH = Path(__file__).resolve().parent / "kaayfi.sqlite"

SCHEMA = """
CREATE TABLE etablissement (
    id INTEGER PRIMARY KEY,
    nom TEXT NOT NULL UNIQUE,
    logo TEXT
);
CREATE TABLE site (
    id INTEGER PRIMARY KEY,
    etablissement_id INTEGER NOT NULL REFERENCES etablissement(id),
    adresse TEXT NOT NULL,
    horaires TEXT NOT NULL,
    ordre INTEGER NOT NULL
);
CREATE TABLE telephone (
    id INTEGER PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES site(id),
    affichage TEXT NOT NULL,
    e164 TEXT NOT NULL
);
CREATE TABLE met (
    id INTEGER PRIMARY KEY,
    etablissement_id INTEGER NOT NULL REFERENCES etablissement(id),
    type TEXT NOT NULL,
    nom TEXT NOT NULL,
    composition TEXT NOT NULL,
    prix_texte TEXT NOT NULL,
    prix_min INTEGER,
    page INTEGER,
    image TEXT
);
CREATE INDEX met_etab ON met(etablissement_id);
CREATE INDEX met_prix ON met(prix_min);
CREATE VIRTUAL TABLE met_fts USING fts5(
    met_id UNINDEXED,
    nom,
    composition,
    type,
    etablissement,
    alias,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'").replace("`", "'")
    return text.lower()


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(text))


def parse_prices(text: str) -> list[int]:
    nums = []
    for match in re.finditer(r"\d{1,2}(?:\s\d{3})+|\d{3,6}", text or ""):
        value = int(match.group().replace(" ", ""))
        if 100 <= value <= 90000:
            nums.append(value)
    return nums


def parse_phones(raw: str) -> list[tuple[str, str]]:
    found = []
    for part in re.split(r"\s*/\s*", raw or ""):
        digits = re.sub(r"\D", "", part)
        if digits.startswith("00221"):
            digits = digits[2:]
        if digits.startswith("221") and len(digits) >= 12:
            national = digits[3:12]
        elif len(digits) == 9:
            national = digits
        else:
            continue
        affichage = f"{national[:2]} {national[2:5]} {national[5:7]} {national[7:9]}"
        found.append((affichage, "+221" + national))
    return found


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    if os.environ.get("KAAYFI_READONLY") == "1":
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def build(path: Path = DB_PATH) -> dict:
    if path.exists():
        path.unlink()
    conn = connect(path)
    conn.executescript(SCHEMA)

    ids: dict[str, int] = {}

    def etab_id(nom: str) -> int:
        if nom not in ids:
            cur = conn.execute("INSERT INTO etablissement(nom) VALUES (?)", (nom,))
            ids[nom] = cur.lastrowid
        return ids[nom]

    with CONTACTS.open(encoding="utf-8-sig", newline="") as handle:
        for ordre, row in enumerate(csv.DictReader(handle)):
            eid = etab_id(row["etablissement"])
            cur = conn.execute(
                "INSERT INTO site(etablissement_id, adresse, horaires, ordre) VALUES (?,?,?,?)",
                (eid, row["adresse"].strip(), row["horaires"].strip(), ordre),
            )
            for affichage, e164 in parse_phones(row["telephone"]):
                conn.execute(
                    "INSERT INTO telephone(site_id, affichage, e164) VALUES (?,?,?)",
                    (cur.lastrowid, affichage, e164),
                )

    with METS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            eid = etab_id(row["etablissement"])
            prices = parse_prices(row["prix"])
            cur = conn.execute(
                """INSERT INTO met(etablissement_id, type, nom, composition, prix_texte, prix_min, page)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    eid,
                    row["type"].strip(),
                    row["nom"].strip(),
                    row["composition"].strip(),
                    row["prix"].strip(),
                    min(prices) if prices else None,
                    int(row["page"]) if row["page"].isdigit() else None,
                ),
            )
            nom = row["nom"].strip()
            conn.execute(
                "INSERT INTO met_fts(met_id, nom, composition, type, etablissement, alias) VALUES (?,?,?,?,?,?)",
                (
                    cur.lastrowid,
                    nom,
                    row["composition"].strip(),
                    row["type"].strip(),
                    row["etablissement"].strip(),
                    squash(row["etablissement"] + " " + nom),
                ),
            )

    conn.commit()
    stats = {
        "etablissements": conn.execute("SELECT COUNT(*) FROM etablissement").fetchone()[0],
        "sites": conn.execute("SELECT COUNT(*) FROM site").fetchone()[0],
        "telephones": conn.execute("SELECT COUNT(*) FROM telephone").fetchone()[0],
        "mets": conn.execute("SELECT COUNT(*) FROM met").fetchone()[0],
    }
    conn.close()
    return stats


if __name__ == "__main__":
    print(build())
