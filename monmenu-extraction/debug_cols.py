#!/usr/bin/env python3
import json, sys
from pathlib import Path

W, H = 595.276, 841.89

def load(page):
    data = json.load(open(f"/Users/mac/Kaayfi/monmenu-extraction/ocr/page_{page:03d}.json"))
    lines = []
    for L in data["lines"]:
        x = L["x"] * W
        w = L["w"] * W
        h = L["h"] * H
        y = (1 - (L["y"] + L["h"])) * H
        t = " ".join(L["t"].split())
        if not t:
            continue
        lines.append({"t": t, "x": x, "y": y, "w": w, "h": h, "c": L["c"]})
    return lines

def columns(lines):
    bins = [0] * 600
    for L in lines:
        if not (140 < L["y"] < 810):
            continue
        if L["w"] > 420:
            continue
        a = int(max(0, L["x"]))
        b = int(min(599, L["x"] + min(L["w"], 280)))
        for i in range(a, b + 1):
            bins[i] += 1
    # smooth
    sm = []
    for i in range(600):
        sm.append(sum(bins[max(0, i-2):i+3]))
    gaps = []
    in_gap = False
    start = 0
    for i, v in enumerate(sm):
        if v == 0 and not in_gap:
            in_gap = True
            start = i
        elif v > 0 and in_gap:
            in_gap = False
            if i - start >= 16 and 20 < start < 575:
                gaps.append((start, i))
    # column bounds
    cuts = [0]
    for a, b in gaps:
        cuts.append((a + b) // 2)
    cuts.append(595)
    # merge narrow
    bounds = list(zip(cuts, cuts[1:]))
    bounds = [(a, b) for a, b in bounds if b - a > 35]
    return bounds, gaps

def assign(lines, bounds):
    cols = [[] for _ in bounds]
    for L in lines:
        cx = L["x"] + min(L["w"], 40) * 0  # left edge
        # use left x
        placed = False
        for i, (a, b) in enumerate(bounds):
            if a - 8 <= L["x"] <= b:
                cols[i].append(L)
                placed = True
                break
        if not placed:
            # nearest
            i = min(range(len(bounds)), key=lambda i: abs(L["x"] - bounds[i][0]))
            cols[i].append(L)
    for c in cols:
        c.sort(key=lambda L: (L["y"], L["x"]))
    return cols

page = int(sys.argv[1])
lines = load(page)
bounds, gaps = columns(lines)
print("GAPS", gaps)
print("BOUNDS", bounds)
cols = assign(lines, bounds)
for i, c in enumerate(cols):
    print(f"\n===== COL {i} n={len(c)} bounds={bounds[i]} =====")
    for L in c:
        print(f"  y={L['y']:6.1f} x={L['x']:6.1f} w={L['w']:5.1f} h={L['h']:4.1f} {L['t'][:110]}")
