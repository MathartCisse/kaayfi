#!/usr/bin/env python3
"""Site local : chercher un plat et appeler l'établissement."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from catalogue import CONTACTS, DB_PATH, METS, build
from search import dish, home, lieu_proche, menu, search, suggest

STATIC = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = 8765

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def ensure_db() -> None:
    try:
        sources = [METS.stat().st_mtime, CONTACTS.stat().st_mtime]
    except OSError:
        return
    if not DB_PATH.exists() or DB_PATH.stat().st_mtime < max(sources):
        stats = build(DB_PATH)
        print("Base reconstruite :", stats)


class App(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/search":
            qs = parse_qs(parsed.query)
            query = qs.get("q", [""])[0][:120]
            raw_max = qs.get("prix_max", [""])[0]
            raw_min = qs.get("prix_min", [""])[0]
            prix_max = int(raw_max) if raw_max.isdigit() else None
            plancher = int(raw_min) if raw_min.isdigit() else None
            ou = qs.get("ou", [""])[0][:80]
            payload = search(query, prix_max=prix_max, plancher=plancher, ou=ou or None)
            self._json(payload)
            return
        if parsed.path == "/api/suggest":
            qs = parse_qs(parsed.query)
            kind = qs.get("kind", ["met"])[0]
            if kind not in ("met", "lieu"):
                kind = "met"
            self._json(suggest(qs.get("q", [""])[0][:80], kind))
            return
        if parsed.path == "/api/home":
            qs = parse_qs(parsed.query)
            raw_heure = qs.get("heure", [""])[0]
            heure = int(raw_heure) if raw_heure.isdigit() and int(raw_heure) <= 23 else None
            ou = qs.get("ou", [""])[0][:80]
            self._json(home(ou=ou or None, heure=heure))
            return
        if parsed.path == "/api/lieu":
            qs = parse_qs(parsed.query)
            try:
                lat = float(qs.get("lat", [""])[0])
                lng = float(qs.get("lng", [""])[0])
            except ValueError:
                self._json({"texte": ""})
                return
            self._json({"texte": lieu_proche(lat, lng)})
            return
        if parsed.path == "/api/menu":
            qs = parse_qs(parsed.query)
            payload = menu(qs.get("e", [""])[0][:120])
            if not payload:
                self._send(404, "application/json; charset=utf-8", b'{"erreur":"introuvable"}')
                return
            self._json(payload)
            return
        if parsed.path == "/api/plat":
            qs = parse_qs(parsed.query)
            raw_id = qs.get("id", [""])[0]
            payload = dish(int(raw_id), qs.get("e", [""])[0][:120]) if raw_id.isdigit() else None
            if not payload:
                self._send(404, "application/json; charset=utf-8", b'{"erreur":"introuvable"}')
                return
            self._json(payload)
            return
        rel = "index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            self._send(404, "text/plain; charset=utf-8", b"Introuvable")
            return
        self._send(200, TYPES.get(target.suffix, "application/octet-stream"), target.read_bytes())

    def _json(self, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self._send(200, "application/json; charset=utf-8", body)

    def _send(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(body)

    def log_message(self, fmt: str, *args):
        print("%s %s" % (self.address_string(), fmt % args))


def main():
    from media import attach

    ensure_db()
    print(attach())
    server = ThreadingHTTPServer((HOST, PORT), App)
    print(f"Kaayfi : http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
