"""Build a diagram once; write it as .drawio and as a PNG rendered from the same geometry."""
import math
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

INK = "#1A1A1A"
PALETTE = {
    "node": ("#FFFFFF", "#7F8C9B"), "panel": ("#F5F9FC", "#2C5F8A"), "blue": ("#DCE6F1", "#1F3864"),
    "green": ("#E2EFDA", "#548235"), "yellow": ("#FFF8E1", "#BF9000"), "data": ("#FFFFDE", "#AAAA33"),
    "store": ("#ECECFF", "#9370DB"), "red": ("#FDE9E7", "#C0504D"), "dark": ("#1F3864", "#1F3864"),
}
FONT, BOLD, SYMBOL = "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/seguisym.ttf"
SHAPES = {"rounded": "rounded=1;arcSize=22;", "pill": "rounded=1;arcSize=50;", "swatch": "rounded=1;arcSize=20;",
          "rect": "rounded=0;", "diamond": "rhombus;strokeWidth=2;", "ellipse": "ellipse;strokeWidth=1.5;",
          "panel": "rounded=1;arcSize=2;verticalAlign=top;container=1;collapsible=0;strokeWidth=1.5;"}


class Diagram:
    def __init__(self, width, height, name):
        self.width, self.height, self.name = width, height, name
        self.cells, self.edges, self.texts = {}, [], []

    def box(self, cid, x, y, w, h, lines, color="node", planned=False, parent=None, shape="rounded", size=13,
            font_color=INK, align="center"):
        self.cells[cid] = dict(x=x, y=y, w=w, h=h, lines=lines, color=color, planned=planned, parent=parent,
                               shape=shape, size=size, font_color=font_color, align=align)

    def text(self, x, y, w, h, s, color=INK, size=11, align="center", bold=False):
        self.texts.append(dict(x=x, y=y, w=w, h=h, s=s, color=color, size=size, align=align, bold=bold))

    def edge(self, src, dst, pts, color="#5B6B7B", dashed=False, width=1.5, both=False, arrow=True):
        """``pts``: absolute polyline from the anchor on ``src`` to the anchor on ``dst``.
        ``src`` and ``dst`` may be None for a free line (sequence-diagram lifelines and messages)."""
        self.edges.append(dict(src=src, dst=dst, pts=pts, color=color, dashed=dashed, width=width, both=both,
                               arrow=arrow))

    def _order(self):
        depth = lambda k: 0 if self.cells[k]["parent"] is None else 1 + depth(self.cells[k]["parent"])
        return sorted(self.cells, key=depth)

    def _html(self, c):
        first, *rest = c["lines"]
        return "<br>".join([f"<b>{first}</b>", *[f'<font style="font-size:11px">{l}</font>' for l in rest]])

    def write_drawio(self, path):
        mxfile = ET.Element("mxfile", host="Electron")
        diagram = ET.SubElement(mxfile, "diagram", name=self.name, id=self.name.replace(" ", "-"))
        model = ET.SubElement(diagram, "mxGraphModel", dx="1600", dy="1000", grid="1", gridSize="10", guides="1",
                              tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1",
                              pageWidth=str(self.width), pageHeight=str(self.height), math="0", shadow="0")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        for cid in self._order():
            c = self.cells[cid]
            fill, stroke = PALETTE[c["color"]]
            st = (f"html=1;whiteSpace=wrap;fillColor={fill};strokeColor={stroke};fontColor={c['font_color']};"
                  f"fontSize={c['size']};align={c['align']};spacingLeft=6;"
                  + ("dashed=1;" if c["planned"] else "") + SHAPES[c["shape"]])
            p = self.cells.get(c["parent"])
            px, py = (p["x"], p["y"]) if p else (0, 0)
            cell = ET.SubElement(root, "mxCell", id=cid, value=self._html(c) if c["lines"] != [""] else "",
                                 style=st, vertex="1", parent=c["parent"] or "1")
            ET.SubElement(cell, "mxGeometry", {"x": str(c["x"] - px), "y": str(c["y"] - py), "width": str(c["w"]),
                                               "height": str(c["h"]), "as": "geometry"})
        for n, e in enumerate(self.edges):
            (sx, sy), (dx, dy) = e["pts"][0], e["pts"][-1]
            st = ("edgeStyle=none;rounded=0;html=1;endArrow=block;endFill=1;"
                  f"strokeColor={e['color']};strokeWidth={e['width']};")
            if e["src"] is not None:
                s = self.cells[e["src"]]
                st += f"exitX={(sx - s['x']) / s['w']:.4f};exitY={(sy - s['y']) / s['h']:.4f};exitDx=0;exitDy=0;exitPerimeter=0;"
            if e["dst"] is not None:
                dcell = self.cells[e["dst"]]
                st += f"entryX={(dx - dcell['x']) / dcell['w']:.4f};entryY={(dy - dcell['y']) / dcell['h']:.4f};entryDx=0;entryDy=0;entryPerimeter=0;"
            st += "dashed=1;" if e["dashed"] else ""
            st += "startArrow=block;startFill=1;" if e["both"] else ""
            st += "" if e["arrow"] else "endArrow=none;"
            ends = {k: v for k, v in (("source", e["src"]), ("target", e["dst"])) if v is not None}
            cell = ET.SubElement(root, "mxCell", id=f"e{n}", style=st, edge="1", parent="1", **ends)
            geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
            if e["src"] is None:
                ET.SubElement(geo, "mxPoint", x=str(sx), y=str(sy), **{"as": "sourcePoint"})
            if e["dst"] is None:
                ET.SubElement(geo, "mxPoint", x=str(dx), y=str(dy), **{"as": "targetPoint"})
            if len(e["pts"]) > 2:
                arr = ET.SubElement(geo, "Array", {"as": "points"})
                for px, py in e["pts"][1:-1]:
                    ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
        for n, t in enumerate(self.texts):
            st = (f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={t['align']};verticalAlign=middle;"
                  f"fontColor={t['color']};fontSize={t['size']};" + ("fontStyle=1;" if t["bold"] else ""))
            cell = ET.SubElement(root, "mxCell", id=f"t{n}", value=t["s"].replace("\n", "<br>"), style=st, vertex="1", parent="1")
            ET.SubElement(cell, "mxGeometry", {"x": str(t["x"]), "y": str(t["y"]), "width": str(t["w"]),
                                               "height": str(t["h"]), "as": "geometry"})
        ET.indent(mxfile)
        with open(path, "wb") as f:
            f.write(ET.tostring(mxfile, encoding="utf-8"))

    def render_png(self, path, scale=2.0):
        S = scale
        img = Image.new("RGB", (int(self.width * S), int(self.height * S)), "white")
        draw = ImageDraw.Draw(img)
        problems = []
        font = lambda size, bold=False: ImageFont.truetype(BOLD if bold else FONT, int(size * S))
        symbol = lambda size: ImageFont.truetype(SYMBOL, int(size * S))
        width_of = lambda s, f, size: sum(draw.textlength(ch, font=symbol(size) if ord(ch) > 0x2400 else f) for ch in s)

        def put(s, x, y, f, size, color):
            for ch in s:
                g = symbol(size) if ord(ch) > 0x2400 else f
                draw.text((x, y), ch, fill=color, font=g)
                x += draw.textlength(ch, font=g)

        def outline(pts, color, width, dashed):
            if not dashed:
                draw.line(pts + [pts[0]], fill=color, width=width, joint="curve")
                return
            path, on, left = pts + [pts[0]], True, 9 * S
            for a, b in zip(path, path[1:]):
                seg, t = math.dist(a, b), 0.0
                while t < seg:
                    step = min(left, seg - t)
                    if on:
                        draw.line([(a[0] + (b[0] - a[0]) * t / seg, a[1] + (b[1] - a[1]) * t / seg),
                                   (a[0] + (b[0] - a[0]) * (t + step) / seg, a[1] + (b[1] - a[1]) * (t + step) / seg)],
                                  fill=color, width=width)
                    t += step
                    left -= step
                    if left <= 1e-6:
                        on, left = not on, (9 if not on else 6) * S

        def rounded(x0, y0, x1, y1, r):
            pts = []
            for cx, cy, a0 in [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]:
                pts += [(cx + r * math.cos(math.radians(a0 + i * 10)), cy + r * math.sin(math.radians(a0 + i * 10))) for i in range(10)]
            return pts

        for cid in self._order():
            c = self.cells[cid]
            fill, stroke = PALETTE[c["color"]]
            x0, y0, x1, y1 = (v * S for v in (c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]))
            if c["shape"] == "diamond":
                pts = [((x0 + x1) / 2, y0), (x1, (y0 + y1) / 2), ((x0 + x1) / 2, y1), (x0, (y0 + y1) / 2)]
            elif c["shape"] == "ellipse":
                cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
                pts = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in range(0, 360, 6)]
            elif c["shape"] == "rect":
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            else:
                r = {"pill": (y1 - y0) / 2, "panel": 6 * S, "swatch": 5 * S}.get(c["shape"], min(14 * S, (y1 - y0) / 2.5))
                pts = rounded(x0, y0, x1, y1, r)
            draw.polygon(pts, fill=fill)
            outline(pts, stroke, int((2 if c["shape"] == "diamond" or c["color"] in ("blue", "dark") else 1.4) * S), c["planned"])
            if c["lines"] == [""]:
                continue
            sizes = [(l, c["size"] if i == 0 else 11, i == 0) for i, l in enumerate(c["lines"])]
            total = sum(sz * 1.25 * S for _, sz, _ in sizes)
            y = y0 + 6 * S if c["shape"] == "panel" else (y0 + y1) / 2 - total / 2
            limit = (x1 - x0) * {"diamond": 0.62, "ellipse": 0.8}.get(c["shape"], 0.94)
            for l, sz, b in sizes:
                f = font(sz, b)
                w = width_of(l, f, sz)
                if w > limit:
                    problems.append(f"{c['lines'][0]}: '{l}' {w / S:.0f}px > {limit / S:.0f}")
                put(l, x0 + 8 * S if c["align"] == "left" else (x0 + x1) / 2 - w / 2, y, f, sz, c["font_color"])
                y += sz * 1.25 * S
            if total > (y1 - y0) + 2:
                problems.append(f"{c['lines'][0]}: text taller than box")

        for e in self.edges:
            pts = [(x * S, y * S) for x, y in e["pts"]]
            wd = int(e["width"] * S)
            if e["dashed"]:
                for a, b in zip(pts, pts[1:]):
                    seg = math.dist(a, b)
                    for i in range(0, int(seg), int(16 * S)):
                        t0, t1 = i / seg, min(1, (i + 9 * S) / seg)
                        draw.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                                   (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=e["color"], width=wd)
            else:
                draw.line(pts, fill=e["color"], width=wd, joint="curve")
            heads = ([(pts[-2], pts[-1])] if e["arrow"] else []) + ([(pts[1], pts[0])] if e["both"] else [])
            for a, b in heads:
                ang = math.atan2(b[1] - a[1], b[0] - a[0])
                draw.polygon([b] + [(b[0] - 11 * S * math.cos(ang + d), b[1] - 11 * S * math.sin(ang + d)) for d in (0.42, -0.42)],
                             fill=e["color"])

        for t in self.texts:
            f = font(t["size"], t["bold"])
            lines = t["s"].split("\n")
            y = (t["y"] + t["h"] / 2) * S - len(lines) * t["size"] * 1.25 * S / 2
            for l in lines:
                w = width_of(l, f, t["size"])
                if w > t["w"] * S + 1:
                    problems.append(f"label '{l}' {w / S:.0f}px > {t['w']}")
                x = {"left": t["x"] * S, "center": (t["x"] + t["w"] / 2) * S - w / 2, "right": (t["x"] + t["w"]) * S - w}[t["align"]]
                put(l, x, y, f, t["size"], t["color"])
                y += t["size"] * 1.25 * S
        img.save(path)
        return problems
