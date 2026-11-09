#!/usr/bin/env python3
"""Dump positioned text spans from Mon Menu PDF."""
import json
import fitz

PDF = "/Users/mac/Downloads/monmenu2025.pdf"
OUT = "/Users/mac/Kaayfi/monmenu-extraction/raw"

doc = fitz.open(PDF)
for i, page in enumerate(doc):
    spans = []
    d = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                text = s["text"]
                if not text or not text.strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                spans.append({
                    "t": text,
                    "x": round(x0, 1),
                    "y": round(y0, 1),
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "sz": round(s["size"], 1),
                    "font": s["font"],
                    "flags": s["flags"],
                    "color": s["color"],
                })
    path = f"{OUT}/page_{i+1:03d}.json"
    with open(path, "w") as f:
        json.dump({"page": i + 1, "w": page.rect.width, "h": page.rect.height, "spans": spans}, f, ensure_ascii=False)
    print(i + 1, len(spans))
