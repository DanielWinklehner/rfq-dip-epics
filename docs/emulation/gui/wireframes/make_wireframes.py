#!/usr/bin/env python3
"""Generate the T14 GUI layout wireframes (SVG, 1600 x 900).

Standard library only. Run from anywhere:

    python3 docs/emulation/gui/wireframes/make_wireframes.py

The SVG files are written next to this script. Grayscale throughout; the alarm
colours (MINOR, MAJOR, INVALID) appear only where they show how a severity looks.
Values are plausible, not measured. PV names follow docs/emulation/DESIGN.md.
"""
import os
from html import escape

W, H = 1600, 900
OUT = os.path.dirname(os.path.abspath(__file__))
FONT = "DejaVu Sans, Verdana, Arial, sans-serif"

# grayscale palette
BG = "#f2f2f2"
PANEL = "#ffffff"
LINE = "#9e9e9e"
DARK = "#424242"
TXT = "#212121"
MUTED = "#757575"
BAR = "#3c3c3c"
LIGHT = "#e0e0e0"

# severity styles: fill, stroke, stroke width, text colour, marker
SEV = {
    "ok":      dict(fill=PANEL, stroke=LINE, sw=1, txt=TXT, mark=""),
    "minor":   dict(fill="#ffe8a3", stroke="#e6a100", sw=2, txt=TXT, mark="▲"),
    "major":   dict(fill="#f6c4c0", stroke="#d32f2f", sw=2.5, txt="#7f0000", mark="■"),
    "invalid": dict(fill="#ecd7f3", stroke="#8e24aa", sw=2.5, txt="#4a148c", mark="?"),
    "disc":    dict(fill="#e6e6e6", stroke="#9e9e9e", sw=1.5, txt=MUTED, mark="×"),
}


def tw(s, size):
    """Rough text width in px for DejaVu Sans."""
    return len(s) * size * 0.6


class Svg:
    def __init__(self, name, caption):
        self.name = name
        self.p = []
        self.p.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" font-family="{FONT}">')
        self.p.append(f'<title>{escape(caption)}</title>')
        self.p.append(
            '<defs><pattern id="hatch" width="12" height="12" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><rect width="12" height="12" fill="#5a5a5a"/>'
            '<rect width="6" height="12" fill="#6e6e6e"/></pattern>'
            '<pattern id="hatchc" width="12" height="12" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><rect width="12" height="12" fill="#0d47a1"/>'
            '<rect width="6" height="12" fill="#1565c0"/></pattern>'
            '<marker id="arr" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
            '<path d="M0,0 L10,4 L0,8 z" fill="#616161"/></marker></defs>')
        self.rect(0, 0, W, H, fill=BG, stroke="none")
        # caption strip
        self.rect(0, 0, W, 24, fill="#d6d6d6", stroke="none")
        self.text(10, 17, caption, 13, weight="bold")
        self.text(W - 10, 17, "MIST-2 GUI wireframe · 1600 × 900 · T14", 11,
                  anchor="end", fill=MUTED)

    # primitives -----------------------------------------------------------
    def raw(self, s):
        self.p.append(s)

    def rect(self, x, y, w, h, fill=PANEL, stroke=LINE, sw=1, rx=0, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                      f'stroke="{stroke}" stroke-width="{sw}"{d}{o}/>')

    def text(self, x, y, s, size=12, weight="normal", anchor="start", fill=TXT, italic=False):
        st = ' font-style="italic"' if italic else ""
        self.p.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
                      f'text-anchor="{anchor}" fill="{fill}"{st}>{escape(s)}</text>')

    def line(self, x1, y1, x2, y2, stroke=DARK, sw=1.2, dash=None, arrow=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        a = ' marker-end="url(#arr)"' if arrow else ""
        self.p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
                      f'stroke-width="{sw}"{d}{a}/>')

    def path(self, d, stroke=DARK, sw=1.2, fill="none", dash=None):
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        self.p.append(f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" fill="{fill}"{ds}/>')

    def circle(self, cx, cy, r, fill=PANEL, stroke=DARK, sw=1.2):
        self.p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" '
                      f'stroke-width="{sw}"/>')

    def group(self, tx, ty, sc=1.0):
        self.p.append(f'<g transform="translate({tx},{ty}) scale({sc})">')

    def end(self):
        self.p.append('</g>')

    def save(self):
        self.p.append('</svg>')
        path = os.path.join(OUT, self.name + ".svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.p) + "\n")
        return path

    # widgets --------------------------------------------------------------
    def lamp(self, cx, cy, state, r=6):
        """state: on, off, fault, minor, invalid, disc"""
        if state == "on":
            self.circle(cx, cy, r, fill=DARK, stroke=DARK)
        elif state == "off":
            self.circle(cx, cy, r, fill=PANEL, stroke=DARK)
        elif state == "fault":
            self.circle(cx, cy, r, fill=SEV["major"]["stroke"], stroke=SEV["major"]["stroke"])
        elif state == "minor":
            self.circle(cx, cy, r, fill=SEV["minor"]["stroke"], stroke=SEV["minor"]["stroke"])
        elif state == "invalid":
            self.circle(cx, cy, r, fill=SEV["invalid"]["fill"], stroke=SEV["invalid"]["stroke"], sw=2)
        else:
            self.circle(cx, cy, r, fill=LIGHT, stroke=MUTED)
            self.line(cx - r * .6, cy - r * .6, cx + r * .6, cy + r * .6, stroke=MUTED)

    def field(self, x, y, w, label, value, unit="", sev="ok", inp=False, h=36, vsize=15):
        """Outlined text field like RAS TextInput / TextOutput (MUI outlined)."""
        s = SEV[sev]
        fill = s["fill"]
        if inp and sev == "ok":
            fill = "#fafafa"
        self.rect(x, y, w, h, fill=fill, stroke=s["stroke"] if sev != "ok" else (DARK if inp else LINE),
                  sw=s["sw"] if sev != "ok" else (1.4 if inp else 1), rx=4,
                  dash="4 3" if sev == "disc" else None)
        # label notch
        lab = label + ("  ✎" if inp else "")
        lw = tw(lab, 10) + 6
        self.rect(x + 7, y - 6, lw, 11, fill=BG if sev == "ok" else BG, stroke="none")
        self.text(x + 10, y + 3, lab, 10, fill=MUTED)
        if sev == "invalid":
            self.text(x + 9, y + h - 11, "INVALID", vsize - 2, weight="bold", fill=s["txt"])
            self.text(x + w - 8, y + h - 11, "?", 13, anchor="end", weight="bold", fill=s["txt"])
        elif sev == "disc":
            self.text(x + 9, y + h - 12, "no connection", vsize - 3, italic=True, fill=MUTED)
            self.text(x + w - 8, y + h - 11, "×", 14, anchor="end", fill=MUTED)
        else:
            self.text(x + 9, y + h - 11, value, vsize, weight="bold" if not inp else "normal",
                      fill=s["txt"])
            u = unit + ("  " + s["mark"] if s["mark"] else "")
            if u:
                self.text(x + w - 8, y + h - 12, u, 12, anchor="end", fill=s["txt"] if sev != "ok" else MUTED)

    def toggle(self, x, y, w, state_on, on="ON", off="OFF", label=None, h=30, sev="ok"):
        """RAS ToggleButton look plus a read-back lamp."""
        if label:
            self.text(x, y - 5, label, 11, fill=MUTED)
        s = SEV[sev]
        self.rect(x, y, w, h, fill=DARK if state_on else PANEL,
                  stroke=s["stroke"] if sev != "ok" else DARK, sw=s["sw"] if sev != "ok" else 1.2, rx=4)
        self.text(x + w / 2, y + h / 2 + 5, on if state_on else off, 12, weight="bold",
                  anchor="middle", fill=PANEL if state_on else DARK)

    def button(self, x, y, w, h, label, kind="outline", size=12):
        if kind == "filled":
            self.rect(x, y, w, h, fill=DARK, stroke=DARK, rx=4)
            self.text(x + w / 2, y + h / 2 + size * 0.36, label, size, weight="bold", anchor="middle",
                      fill=PANEL)
        elif kind == "danger":
            self.rect(x, y, w, h, fill="#f5f5f5", stroke="#111111", sw=2.5, rx=4)
            self.text(x + w / 2, y + h / 2 + size * 0.36, label, size, weight="bold", anchor="middle",
                      fill="#111111")
        elif kind == "ghost":
            self.rect(x, y, w, h, fill="none", stroke=MUTED, rx=4, dash="4 3")
            self.text(x + w / 2, y + h / 2 + size * 0.36, label, size, anchor="middle", fill=MUTED)
        else:
            self.rect(x, y, w, h, fill=PANEL, stroke=DARK, rx=4)
            self.text(x + w / 2, y + h / 2 + size * 0.36, label, size, anchor="middle", fill=DARK)

    def card(self, x, y, w, h, legend, link=None, sev="ok"):
        """fieldset + legend look of the 2023 GUI."""
        s = SEV[sev]
        self.rect(x, y, w, h, fill=PANEL, stroke=s["stroke"] if sev != "ok" else LINE,
                  sw=s["sw"] if sev != "ok" else 1, rx=4)
        lw = tw(legend, 13) + 12
        self.rect(x + 10, y - 8, lw, 16, fill=BG, stroke="none")
        self.text(x + 16, y + 5, legend, 13, weight="bold")
        if link:
            lk = tw(link, 11) + 10
            self.rect(x + w - lk - 10, y - 8, lk, 16, fill=BG, stroke="none")
            self.text(x + w - 15, y + 4, link, 11, anchor="end", fill=DARK)

    def trend(self, x, y, w, h, title, series, unit, ticks, log=False):
        self.card(x, y, w, h, title)
        px, py, pw, ph = x + 70, y + 22, w - 90, h - 62
        self.rect(px, py, pw, ph, fill="#fbfbfb", stroke=LIGHT)
        for i, t in enumerate(ticks):
            yy = py + ph - i * ph / (len(ticks) - 1)
            self.line(px, yy, px + pw, yy, stroke="#ececec", sw=1)
            self.text(px - 6, yy + 4, t, 10, anchor="end", fill=MUTED)
        self.text(px - 6, py - 6, unit, 10, anchor="end", fill=MUTED)
        for i, lab in enumerate(["-10 min", "-7.5", "-5", "-2.5", "now"]):
            self.text(px + i * pw / 4, py + ph + 14, lab, 10, anchor="middle", fill=MUTED)
        dashes = [None, "6 3", "2 3", "8 3 2 3"]
        shades = ["#212121", "#616161", "#9e9e9e", "#424242"]
        lx = px
        for i, (lab, ys) in enumerate(series):
            pts = []
            n = len(ys)
            for j, v in enumerate(ys):
                pts.append(f"{px + j * pw / (n - 1):.1f},{py + ph - v * ph:.1f}")
            self.path("M" + " L".join(pts), stroke=shades[i % 4], sw=1.6, dash=dashes[i % 4])
            self.line(lx, y + h - 14, lx + 22, y + h - 14, stroke=shades[i % 4], sw=1.6,
                      dash=dashes[i % 4])
            self.text(lx + 27, y + h - 10, lab, 11, fill=DARK)
            lx += 40 + tw(lab, 11)

    def tag(self, x, y, w, title, rows, sev="ok", lamp=None, selected=False, size=11.5):
        """Synoptic value tag. rows: list of (label, value, sev)."""
        h = 20 + 17 * len(rows) + 3
        s = SEV[sev]
        if selected:
            self.rect(x - 4, y - 4, w + 8, h + 8, fill="none", stroke="#000000", sw=3, rx=6)
        self.rect(x, y, w, h, fill=s["fill"] if sev != "ok" else PANEL,
                  stroke=s["stroke"] if sev != "ok" else LINE, sw=s["sw"] if sev != "ok" else 1, rx=4,
                  dash="4 3" if sev == "disc" else None)
        self.text(x + 6, y + 14, title, size, weight="bold", fill=s["txt"] if sev != "ok" else TXT)
        if lamp:
            self.lamp(x + w - 10, y + 10, lamp, r=5)
        for i, (lab, val, rs) in enumerate(rows):
            yy = y + 20 + 17 * i
            if sev == "disc":
                rs = sev
            r = SEV[rs]
            if rs in ("minor", "major"):
                self.rect(x + 2, yy + 1, w - 4, 16, fill=r["fill"], stroke=r["stroke"], sw=1.2, rx=2)
            self.text(x + 6, yy + 13, lab, size - 1, fill=MUTED if rs == "ok" else r["txt"])
            if rs == "invalid":
                val = "INVALID"
            elif rs == "disc":
                val = "no conn."
            mark = (" " + r["mark"]) if r["mark"] and rs not in ("invalid", "disc") else ""
            self.text(x + w - 6, yy + 13, val + mark, size, weight="bold", anchor="end",
                      fill=r["txt"] if rs != "ok" else TXT)
        return h


# ---------------------------------------------------------------------------- frame
TABS = ["Overview", "Plasma generator", "Extraction", "Vacuum & gas", "Cooling & interlocks",
        "Diagnostics", "Trends"]


def appbar(s, tabs=None, active=None, expert=None, title="MIST-2 Ion Source"):
    y = 24
    s.rect(0, y, W, 48, fill=BAR, stroke="none")
    for i in range(3):
        s.line(16, y + 17 + i * 7, 34, y + 17 + i * 7, stroke=PANEL, sw=2)
    s.text(50, y + 30, title, 17, weight="bold", fill=PANEL)
    if tabs:
        x = 240
        for t in tabs:
            tw_ = tw(t, 13) + 26
            if t == active:
                s.rect(x, y + 44, tw_, 4, fill=PANEL, stroke="none")
                s.text(x + tw_ / 2, y + 30, t, 13, weight="bold", anchor="middle", fill=PANEL)
            else:
                s.text(x + tw_ / 2, y + 30, t, 13, anchor="middle", fill="#d0d0d0")
            x += tw_
    # right cluster
    s.text(W - 18, y + 31, "⋮", 20, anchor="middle", fill=PANEL, weight="bold")
    s.rect(W - 130, y + 10, 96, 28, fill="none", stroke="#bdbdbd", rx=4, dash="4 3")
    s.text(W - 82, y + 29, "PDF report", 12, anchor="middle", fill="#bdbdbd")
    s.rect(W - 262, y + 8, 120, 32, fill="#fafafa", stroke="#000000", sw=2.5, rx=4)
    s.text(W - 202, y + 29, "ALL HV OFF", 13, weight="bold", anchor="middle", fill="#000000")
    if expert is not None:
        ex = W - 400
        s.rect(ex, y + 10, 124, 28, fill=PANEL if expert else "none", stroke=PANEL, rx=14)
        s.text(ex + 62, y + 29, "Expert " + ("ON" if expert else "off"), 12, weight="bold",
               anchor="middle", fill=BAR if expert else PANEL)


def status_strip(s, sim=True, ilk="closed"):
    """Emulator banner (left) and IOC / interlock state (right). 28 px high."""
    y = 72
    if sim:
        s.rect(0, y, W, 28, fill="url(#hatch)", stroke="none")
        s.rect(8, y + 3, 640, 22, fill="#2b2b2b", stroke="none", rx=3)
        s.text(16, y + 19, "EMULATOR — rack IOC and HV IOC report mode sim. No hardware is connected.",
               12.5, weight="bold", fill=PANEL)
    else:
        s.rect(0, y, W, 28, fill="#e8e8e8", stroke="none")
    x = W - 10
    items = [("Interlock: doors closed, permit yes", "on"), ("HV IOC  sim  ♥ 1 s", "on"),
             ("Rack IOC  sim  ♥ 1 s", "on")]
    for t, st in items:
        w = tw(t, 11.5) + 30
        x -= w
        s.rect(x, y + 4, w - 6, 20, fill=PANEL, stroke=DARK, rx=10)
        s.lamp(x + 11, y + 14, st, r=4.5)
        s.text(x + 20, y + 18, t, 11.5, fill=TXT)


TOP = 100  # first free y below app bar and status strip


# ---------------------------------------------------------------------------- synoptic
def synoptic(s, ox, oy, sc, detail="full", selected=None):
    """Source synoptic in a 1200 x 560 box. detail: full | reads."""
    full = detail == "full"
    s.group(ox, oy, sc)
    s.rect(0, 0, 1200, 560, fill=PANEL, stroke=LINE, rx=4)
    # HV platform
    s.rect(10, 30, 460, 300, fill="#f7f7f7", stroke=DARK, sw=1.5, dash="8 4", rx=6)
    s.text(18, 48, "HV platform (at ion source voltage)", 12, weight="bold", fill=DARK)
    # plasma chamber
    s.rect(250, 70, 150, 150, fill="#eeeeee", stroke=DARK, sw=2, rx=10)
    for i in range(6):  # cusp magnets
        s.rect(258 + i * 23, 63, 12, 7, fill=DARK, stroke="none")
        s.rect(258 + i * 23, 220, 12, 7, fill=DARK, stroke="none")
    s.path("M285,145 l8,-14 l8,28 l8,-28 l8,28 l8,-28 l8,28 l8,-14", stroke="#000", sw=2)
    s.text(325, 205, "plasma chamber", 10.5, anchor="middle", fill=MUTED)
    # supplies on platform
    rows = ([("I set", "185.0 A", "ok"), ("I / U", "182.4 A  5.21 V", "ok"), ("output", "ON", "ok")]
            if full else [("I / U", "182.4 A  5.21 V", "ok")])
    h = s.tag(20, 58, 205, "Filament heating (TDK)", rows, lamp="on", selected=selected == "tdk")
    s.line(225, 58 + h / 2, 285, 145, stroke=DARK, dash="3 2")
    rows = ([("I set", "8.00 A", "ok"), ("I / U", "7.98 A  92.1 V", "ok"), ("output", "ON", "ok")]
            if full else [("I / U", "7.98 A  92.1 V", "ok")])
    y2 = 58 + h + 12
    h2 = s.tag(20, y2, 205, "Discharge (REK)", rows, lamp="on", selected=selected == "rek")
    s.line(225, y2 + h2 / 2, 250, 170, stroke=DARK, dash="3 2")
    y3 = y2 + h2 + 12
    rows = [("TC 1", "35.0 °C", "ok"), ("Back plate", "41.2 °C", "ok"),
            ("Magnet plate", "62.3 °C", "minor"), ("TC 4", "33.8 °C", "ok")]
    if not full:
        rows = [("Back plate", "41.2 °C", "ok"), ("Magnet plate", "62.3 °C", "minor")]
    h3 = s.tag(20, y3, 205, "Thermocouples", rows, sev="ok", selected=selected == "thm")
    s.line(225, y3 + 10, 250, 200, stroke=DARK, dash="3 2")
    # front plate water
    s.tag(290, 240, 170, "Front plate water", [("flow", "1.21 l/min", "ok")])
    # gas line
    s.line(268, 220, 268, 384, stroke=DARK, sw=2)
    s.rect(258, 337, 20, 8, fill=PANEL, stroke=DARK)  # insulating break
    s.text(284, 345, "insulating break (assumed)", 9.5, fill=MUTED)
    valve(s, 268, 364, "v", closed=False)
    s.text(284, 369, "valve 2  MFC shutoff  OPEN", 10.5, fill=DARK)
    rows = ([("set", "1.20 sccm", "ok"), ("flow", "1.19 sccm", "ok")] if full
            else [("flow", "1.19 sccm", "ok")])
    s.tag(215, 384, 170, "Gas (MFC)", rows, selected=selected == "mfc")
    # source voltage
    rows = ([("U set", "15.00 kV", "ok"), ("U / I", "15.00 kV  1.20 mA", "ok")] if full
            else [("U / I", "15.00 kV  1.20 mA", "ok")])
    s.tag(20, 345, 180, "Ion source voltage (AU 1)", rows, lamp="on", selected=selected == "au1",
          size=10.5)
    s.line(110, 345, 110, 330, stroke=DARK, sw=1.5)
    # beam
    s.line(400, 145, 815, 145, stroke="#9e9e9e", sw=5)
    # extraction vessel and electrodes
    s.rect(485, 88, 295, 114, fill="none", stroke=LINE, sw=1.5, rx=4)
    names = [("Puller (AU 2)", 520, "top", "4.20 kV  0.35 mA", "4.20 kV", "ok", "au2"),
             ("Lens 1 (AU 3)", 580, "bot", "6.00 kV  0.02 mA", "6.00 kV", "ok", "au3"),
             ("Lens 2 (AU 5)", 640, "top", "", "", "invalid", "au5"),
             ("Lens 3 (AU 4)", 700, "bot", "not polled", "", "ok", "au4")]
    for nm, ex, pos, ui, us, sv, key in names:
        dim = key == "au4"
        col = "#bdbdbd" if dim else (SEV["invalid"]["stroke"] if sv == "invalid" else "#000")
        s.rect(ex - 4, 95, 8, 42, fill=col, stroke="none")
        s.rect(ex - 4, 153, 8, 42, fill=col, stroke="none")
        if dim:
            rows = [("", "not in use", "ok")]
        elif full:
            rows = [("U set", us or "2.50 kV", "ok"), ("U", ui.split("  ")[0] if ui else "-", sv),
                    ("I", ui.split("  ")[1] if ui else "-", sv)]
        else:
            rows = [("U", ui.split("  ")[0] if ui else "-", sv), ("I", ui.split("  ")[1] if ui else "-", sv)]
        tx = ex - 35
        hh = 20 + 17 * len(rows) + 3
        if pos == "top":
            ty = 80 - hh
            s.line(ex, ty + hh, ex, 95, stroke=col, sw=1, dash="2 2")
        else:
            ty = 212
            s.line(ex, 195, ex, 212, stroke=col, sw=1, dash="2 2")
        s.tag(tx, ty, 118, nm, rows, sev="disc" if False else sv,
              lamp=None if dim else ("invalid" if sv == "invalid" else "on"), selected=selected == key,
              size=10.5)
    # source gauge (nAIM) on extraction vessel
    gauge(s, 765, 80)
    rows = [("p", "2.4e-6 Torr", "ok")] + ([("gauge", "ON", "ok")] if full else [])
    hh = 20 + 17 * len(rows) + 3
    s.tag(730, 80 - 12 - hh, 150, "Source gauge (nAIM)", rows, selected=selected == "naim", size=10.5)
    # vent valve
    s.line(500, 202, 500, 304, stroke=DARK, sw=2)
    valve(s, 500, 304, "h", closed=True)
    s.text(514, 309, "valve 3  vent  CLOSED", 10.5, fill=DARK)
    # diagnostic box
    s.rect(815, 88, 180, 114, fill="#eeeeee", stroke=DARK, sw=2, rx=6)
    s.text(825, 104, "Diagnostic box", 11, weight="bold", fill=DARK)
    s.path("M935,125 h22 v40 h-22", stroke="#000", sw=3)  # cup
    s.line(946, 88, 946, 125, stroke="#000", sw=2)
    gauge(s, 850, 80)
    rows = [("p", "8.1e-7 Torr", "ok")]
    s.tag(888, 22, 140, "Diag. box gauge", rows, selected=selected == "diag")
    s.line(888, 50, 858, 75, stroke=DARK, dash="2 2")
    rows = ([("current", "0.85 mA", "ok"), ("cup", "IN  (valve 4)", "ok"), ("water", "0.48 l/min", "ok")]
            if full else [("current", "0.85 mA", "ok"), ("cup", "IN", "ok")])
    s.tag(820, 212, 150, "Faraday cup", rows, selected=selected == "fc")
    # turbos
    for k, (px, lbl, spd) in enumerate([(770, "Turbo 1", "1200 Hz  0.92 A"),
                                        (990, "Turbo 2", "1200 Hz  0.88 A")]):
        s.line(px, 202, px, 300, stroke=DARK, sw=2)
        pump(s, px, 316)
        s.line(px, 332, px, 470, stroke=DARK, sw=2)
        rows = [("state", "NORMAL", "ok"), ("speed", spd, "ok")]
        if full:
            rows.append(("record age", "3 s", "ok"))
        s.tag(px + 26, 300, 170, lbl, rows, lamp="on",
              selected=selected == f"tp{k+1}")
    # foreline
    s.line(990, 470, 430, 470, stroke=DARK, sw=2)
    valve(s, 700, 470, "h", closed=False)
    s.text(700, 498, "valve 1  foreline", 10.5, anchor="middle", fill=DARK)
    s.text(700, 512, "OPEN", 10.5, weight="bold", anchor="middle", fill=DARK)
    gauge(s, 590, 470)
    s.tag(530, 490, 120, "Foreline (APG)", [("p", "3.2e-2 Torr", "ok")], selected=selected == "apg",
          size=10.5)
    pump(s, 414, 470, rough=True)
    s.text(414, 504, "Roughing pump", 10.5, anchor="middle", fill=MUTED)
    s.text(414, 518, "(no PVs yet)", 10.5, anchor="middle", fill=MUTED)
    # cooling summary and doors
    rows = [("turbo pump flow", "0.62 l/min", "ok"), ("flow 1, flow 5", "unlabelled", "ok"),
            ("7 water temps, max", "31.2 °C", "ok")]
    s.tag(1015, 400, 175, "Cooling (sensor box)", rows if full else rows[:1] + rows[2:],
          selected=selected == "cool", size=10.5)
    s.end()


def valve(s, x, y, orient="h", closed=False):
    f = DARK if closed else PANEL
    if orient == "h":
        s.path(f"M{x-11},{y-8} L{x+11},{y+8} L{x+11},{y-8} L{x-11},{y+8} Z", stroke="#000", sw=1.5, fill=f)
    else:
        s.path(f"M{x-8},{y-11} L{x+8},{y+11} L{x-8},{y+11} L{x+8},{y-11} Z", stroke="#000", sw=1.5, fill=f)


def gauge(s, x, y):
    s.circle(x, y, 9, fill=PANEL, stroke="#000", sw=1.5)
    s.text(x, y + 4, "G", 10, weight="bold", anchor="middle")


def pump(s, x, y, rough=False):
    s.circle(x, y, 16, fill=PANEL, stroke="#000", sw=1.8)
    if rough:
        s.path(f"M{x-10},{y-10} L{x+14},{y} L{x-10},{y+10}", stroke="#000", sw=1.5)
    else:
        s.line(x - 11, y - 11, x + 11, y + 11, stroke="#000", sw=1.5)
        s.line(x - 11, y + 11, x + 11, y - 11, stroke="#000", sw=1.5)


# ============================================================================ option A
def a_overview():
    s = Svg("A1_overview", "Option A · Tabs and cards — Overview page (synoptic with every value)")
    appbar(s, TABS, "Overview")
    status_strip(s)
    synoptic(s, 32, 110, 1.28, "full")
    s.text(32, 852, "Every value sits where it is measured. Click a tag: its subsystem tab opens. "
           "Right-click any value (RAS context menu): PV name, copy, Probe.", 13, fill=DARK)
    s.text(32, 874, "Set points are shown, not edited, on this page. Editing happens on the subsystem tabs.",
           13, fill=DARK)
    return s.save()


def a_vacuum():
    s = Svg("A2_vacuum", "Option A \u00B7 Tabs and cards \u2014 Vacuum & gas tab (device cards, trends below)")
    appbar(s, TABS, "Vacuum & gas")
    status_strip(s)
    y = 122
    # pressures
    s.card(16, y, 560, 150, "Pressures", link="expert \u203A")
    s.field(32, y + 30, 170, "Source (nAIM)", "2.4e-6", "Torr")
    s.field(214, y + 30, 170, "Diagnostic box", "8.1e-7", "Torr")
    s.field(396, y + 30, 170, "Foreline (APG)", "3.2e-2", "Torr")
    s.toggle(32, y + 100, 110, True, "ON", "OFF", label="nAIM gauge (strike)")
    s.lamp(158, y + 115, "on")
    s.text(170, y + 119, "read-back: on", 11, fill=MUTED)
    # turbos
    for k, x in enumerate([592, 912]):
        s.card(x, y, 304, 150, f"Turbo {k+1}  (NT 20)", link="expert \u203A")
        s.toggle(x + 16, y + 30, 90, True, "RUN", "STOP", label=None)
        for j, (lab, st) in enumerate([("accel.", "off"), ("normal", "on"), ("failure", "off")]):
            s.lamp(x + 128 + j * 60, y + 44, st)
            s.text(x + 128 + j * 60, y + 66, lab, 10.5, anchor="middle", fill=MUTED)
        s.field(x + 16, y + 92, 88, "state", "NORMAL", "")
        s.field(x + 112, y + 92, 88, "speed", "1200", "Hz")
        s.field(x + 208, y + 92, 80, "current", "0.9" + str(2 - 2 * k // 2 + 0), "A")
    # MFC
    s.card(1232, y, 352, 150, "Gas (MFC GV50A)", link="expert \u203A")
    s.field(1248, y + 30, 160, "set point", "1.20", "sccm", inp=True)
    s.field(1416, y + 30, 152, "set point read", "1.20", "sccm")
    s.field(1248, y + 92, 160, "flow", "1.19", "sccm")
    s.toggle(1416, y + 98, 152, True, "OPEN", "CLOSED", label="valve 2  MFC shutoff")
    # valves
    y2 = 300
    s.card(16, y2, 880, 168, "Valves (valve box, 8 channels)", link="expert \u203A")
    labels = [("1  Foreline", True), ("2  MFC shutoff", True), ("3  Vent", False),
              ("4  Faraday cup", True), ("5  spare", False), ("6  spare", False), ("7  spare", False),
              ("8  spare", False)]
    for i, (lab, on) in enumerate(labels):
        cx = 32 + (i % 4) * 214
        cy = y2 + 42 + (i // 4) * 66
        s.text(cx, cy - 4, lab, 12, weight="bold" if "spare" not in lab else "normal",
               fill=TXT if "spare" not in lab else MUTED)
        onl, offl = ("IN", "OUT") if "Faraday" in lab else ("OPEN", "CLOSED")
        s.toggle(cx, cy + 4, 120, on, onl, offl)
        s.lamp(cx + 138, cy + 19, "on" if on else "off")
        s.text(cx + 150, cy + 23, "read-back", 10, fill=MUTED)
    s.card(912, y2, 300, 168, "Roughing pump")
    s.text(928, y2 + 50, "No PVs yet (make and model tbd,", 12, fill=MUTED)
    s.text(928, y2 + 68, "controls.yaml: rough1:*).", 12, fill=MUTED)
    s.text(928, y2 + 100, "Card appears when the registry", 12, fill=MUTED)
    s.text(928, y2 + 118, "lists the device.", 12, fill=MUTED)
    s.card(1228, y2, 356, 168, "Vacuum at a glance")
    s.text(1244, y2 + 40, "Same symbols as the overview:", 11.5, fill=MUTED)
    pump(s, 1270, y2 + 90)
    s.text(1270, y2 + 124, "TP 1", 10.5, anchor="middle")
    pump(s, 1330, y2 + 90)
    s.text(1330, y2 + 124, "TP 2", 10.5, anchor="middle")
    valve(s, 1400, y2 + 90, "h", closed=False)
    s.text(1400, y2 + 124, "valve 1", 10.5, anchor="middle")
    gauge(s, 1460, y2 + 90)
    s.text(1460, y2 + 124, "APG", 10.5, anchor="middle")
    pump(s, 1530, y2 + 90, rough=True)
    s.text(1530, y2 + 124, "rough", 10.5, anchor="middle")
    s.text(1244, y2 + 156, "click: back to overview", 10.5, fill=MUTED)
    # trends
    import math
    def wave(a, b, n=60, ph=0.0, noise=0.004):
        return [a + (b - a) * (0.5 + 0.5 * math.tanh((j - 25) / 6.0)) + noise * math.sin(j * 1.7 + ph)
                for j in range(n)]
    s.trend(16, 492, 780, 392, "Pressures (log scale)",
            [("Source (nAIM)", wave(0.45, 0.30, ph=1)), ("Diagnostic box", wave(0.35, 0.24, ph=2)),
             ("Foreline (APG)", wave(0.85, 0.81, ph=3))],
            "Torr", ["1e-8", "1e-6", "1e-4", "1e-2", "1e0"])
    s.trend(812, 492, 772, 392, "Turbo speed",
            [("Turbo 1", wave(0.75, 0.75, ph=0.5)), ("Turbo 2", wave(0.745, 0.745, ph=1.5))],
            "Hz", ["0", "400", "800", "1200", "1600"])
    return s.save()


def expert_rows_lens2():
    return [
        ("AU-20P7-5:voltage:setpoint", "2.50", "NO_ALARM", "", "14:01:40"),
        ("AU-20P7-5:voltage:get", "2.50", "INVALID", "TIMEOUT", "14:02:11"),
        ("AU-20P7-5:voltage:read", "2.48", "INVALID", "TIMEOUT", "14:02:11"),
        ("AU-20P7-5:current:setpoint", "0.10", "NO_ALARM", "", "14:01:40"),
        ("AU-20P7-5:current:get", "0.10", "INVALID", "TIMEOUT", "14:02:11"),
        ("AU-20P7-5:current:read", "0.01", "INVALID", "TIMEOUT", "14:02:11"),
        ("AU-20P7-5:SetToggleOutput", "1", "NO_ALARM", "", "13:55:02"),
        ("AU-20P7-5:OutputIntlk", "1", "NO_ALARM", "", "13:55:02"),
        ("AU-20P7-5:ToggleOutput", "1", "NO_ALARM", "", "13:55:02"),
        ("AU-20P7-5:status:read", "1", "INVALID", "TIMEOUT", "14:02:11"),
        ("AU-20P7-5:read_output_status", "1", "INVALID", "TIMEOUT", "14:02:11"),
        ("AU-20P7-5:power:read", "0.02", "INVALID", "LINK", "14:02:11"),
    ]


def pv_table(s, x, y, w, rows, cols, rh=26, size=12):
    """cols: list of (title, width). rows: tuples matching cols; SEVR column drives colour."""
    s.rect(x, y, w, rh, fill=LIGHT, stroke="none")
    cx = x
    for t, cw in cols:
        s.text(cx + 8, y + rh - 8, t, size - 1, weight="bold", fill=DARK)
        cx += cw
    for i, r in enumerate(rows):
        yy = y + rh * (i + 1)
        sev = "invalid" if "INVALID" in r else ("minor" if "MINOR" in r else "ok")
        if sev != "ok":
            s.rect(x, yy, w, rh, fill=SEV[sev]["fill"], stroke="none")
            s.rect(x, yy, 4, rh, fill=SEV[sev]["stroke"], stroke="none")
        s.line(x, yy + rh, x + w, yy + rh, stroke="#e6e6e6", sw=1)
        cx = x
        for (t, cw), v in zip(cols, r):
            mono = t in ("PV", "PV name")
            ff = 'font-family="DejaVu Sans Mono, monospace" ' if mono else ""
            col = SEV[sev]["txt"] if sev != "ok" else TXT
            s.raw(f'<text x="{cx + 8}" y="{yy + rh - 8}" font-size="{size}" {ff}fill="{col}">'
                  f'{escape(v)}</text>')
            cx += cw
    return y + rh * (len(rows) + 1)


def lens2_diagnosis(s, x, y, w, compact=False):
    s.rect(x, y, w, 96 if not compact else 112, fill=SEV["invalid"]["fill"], stroke=SEV["invalid"]["stroke"],
           sw=2, rx=4)
    title = ("INVALID since 14:02:11, STAT = TIMEOUT" if compact
             else "Why is it purple?  INVALID since 14:02:11, STAT = TIMEOUT")
    s.text(x + 12, y + 22, title, 13, weight="bold", fill=SEV["invalid"]["txt"])
    if compact:
        lines = ["Unit 5 has not answered for 2 min 14 s.",
                 "Lens 1 (unit 3) on the same chain answers:",
                 "chain and adapter are fine, look at the supply.",
                 "Set points are not affected (no reply expected)."]
    else:
        lines = ["Unit 5 has not answered a poll for 2 min 14 s. Lens 1 (unit 3) on the same chain answers, so the",
                 "chain CO-U32 (mat_co) and the adapter work: check the supply, its fiber and its CO-HV board.",
                 "Set point records stay NO_ALARM because the CO protocol does not answer sets (DESIGN.md \u00A72)."]
    for i, l in enumerate(lines):
        s.text(x + 12, y + 44 + i * 18, l, 12, fill=SEV["invalid"]["txt"])


def a_expert():
    s = Svg("A3_expert", "Option A \u00B7 Tabs and cards \u2014 Expert page, opened from the \u2018expert \u203A\u2019 "
            "link of a card (here Lens 2)")
    appbar(s, TABS, "Extraction")
    status_strip(s)
    s.text(16, 126, "Extraction  \u203A  Lens 2 (AU 5)  \u203A  Expert", 15, weight="bold")
    s.text(16, 146, "Own route (/expert/au_lens2): opens in place, or in a second browser tab with middle-click. "
           "Generated from the registry for every device.", 12, fill=MUTED)
    s.button(1404, 110, 180, 32, "\u2039 back to Extraction")
    lens2_diagnosis(s, 16, 160, 1100)
    # device card
    s.card(1132, 172, 452, 300, "Device and communication")
    info = [("model", "Matsusada AU20N7.5 with CO-HV"), ("full scale", "20 kV, 7.5 mA (macros VFS, IFS)"),
            ("IOC", "Rack IOC  (mode sim)"), ("port / chain", "mat_co  (CO-U32)"), ("unit", "5"),
            ("other units on chain", "Lens 1 OK, Lens 3 not polled"), ("last good reply", "14:02:11"),
            ("poll rate (measured)", "monitors 6.4 Hz, status 1 Hz"), ("identity", "none (not a libcom1 device)")]
    for i, (k, v) in enumerate(info):
        s.text(1148, 204 + i * 28, k, 12, fill=MUTED)
        s.text(1310, 204 + i * 28, v, 12, weight="bold")
    s.card(16, 282, 1100, 540, "Raw channels (every record of this device, from the registry)")
    cols = [("PV", 300), ("value", 100), ("SEVR", 110), ("STAT", 110), ("time stamp", 120), ("desc", 360)]
    rows = [r + (d,) for r, d in zip(expert_rows_lens2(),
            ["voltage set point", "set-point echo (CH0?)", "voltage monitor (MN1)", "current set point",
             "set-point echo (CH1?)", "current monitor (MN2)", "output request", "request gated by interlock",
             "output command", "status word (STS)", "output on/off from STS", "U x I"])]
    pv_table(s, 30, 302, 1072, rows, cols)
    s.card(1132, 494, 452, 328, "Actions")
    s.button(1148, 520, 200, 34, "Copy all PV names")
    s.button(1364, 520, 204, 34, "Open in Probe")
    s.button(1148, 566, 200, 34, "Trend all monitors")
    s.button(1364, 566, 204, 34, "Show in overview")
    s.text(1148, 630, "Probe and copy come with RAS (ContextMenu.jsx).", 11.5, fill=MUTED)
    s.text(1148, 650, "Right-click on any value anywhere gives the same", 11.5, fill=MUTED)
    s.text(1148, 670, "menu for that one PV.", 11.5, fill=MUTED)
    s.text(1148, 708, "Emulator only (shown in mode sim):", 11.5, weight="bold", fill=DARK)
    s.button(1148, 720, 200, 30, "Inject fault \u2026", kind="ghost")
    s.button(1364, 720, 204, 30, "Clear fault", kind="ghost")
    s.text(1148, 772, "Talks to the simulator control port,", 11.5, fill=MUTED)
    s.text(1148, 792, "not to the IOC. Hidden with real hardware.", 11.5, fill=MUTED)
    s.text(16, 848, "SEVR and STAT are read as field PVs (record.SEVR, record.STAT). Time stamp from the IOC. "
           "A dead device shows INVALID and the time of its last good reply, never only an old number.",
           12, fill=DARK)
    return s.save()


# ============================================================================ option B
def panel(s, x, y, w, h, title, sub, tabs, active):
    s.rect(x, y, w, h, fill=PANEL, stroke=DARK, sw=1.5, rx=4)
    s.text(x + 14, y + 26, title, 15, weight="bold")
    s.text(x + 14, y + 44, sub, 11, fill=MUTED)
    s.text(x + w - 16, y + 26, "\u00D7", 18, anchor="end", fill=DARK)
    s.text(x + w - 40, y + 25, "\u2922", 14, anchor="end", fill=DARK)
    tx = x + 14
    for t in tabs:
        tw_ = tw(t, 12.5) + 24
        if t == active:
            s.rect(tx, y + 74, tw_, 3, fill=DARK, stroke="none")
            s.text(tx + tw_ / 2, y + 68, t, 12.5, weight="bold", anchor="middle")
        else:
            s.text(tx + tw_ / 2, y + 68, t, 12.5, anchor="middle", fill=MUTED)
        tx += tw_
    s.line(x, y + 77, x + w, y + 77, stroke=LIGHT)


def b_overview():
    s = Svg("B1_overview", "Option B \u00B7 Synoptic with detail panel \u2014 Overview (Lens 2 clicked, "
            "panel shows its controls)")
    appbar(s, TABS, "Overview")
    status_strip(s)
    sc = 0.94
    synoptic(s, 16, 112, sc, "reads", selected="au5")
    px, pw = 1164, 420
    panel(s, px, 112, pw, 772, "Lens 2  (AU 5)", "Matsusada AU20N7.5 \u00B7 Extraction \u00B7 click another element "
          "to switch", ["Controls", "Trend", "Expert"], "Controls")
    yy = 212
    s.field(px + 16, yy, 186, "voltage set", "2.50", "kV", inp=True)
    s.field(px + 218, yy, 186, "current limit set", "0.10", "mA", inp=True)
    s.field(px + 16, yy + 60, 186, "voltage read", "", "kV", sev="invalid")
    s.field(px + 218, yy + 60, 186, "current read", "", "mA", sev="invalid")
    s.toggle(px + 16, yy + 130, 120, True, "OUTPUT ON", "OUTPUT OFF", label="output request")
    s.lamp(px + 160, yy + 145, "invalid")
    s.text(px + 174, yy + 149, "output state: INVALID", 11.5, fill=SEV["invalid"]["txt"])
    lens2_diagnosis(s, px + 12, yy + 186, pw - 24, compact=True)
    s.text(px + 16, yy + 340, "Last 10 min", 12, weight="bold")
    import math
    s.rect(px + 16, yy + 350, pw - 32, 150, fill="#fbfbfb", stroke=LIGHT)
    pts = " L".join(f"{px + 16 + j * (pw - 32) / 59:.1f},{yy + 420 + 6 * math.sin(j):.1f}" for j in range(45))
    s.path("M" + pts, stroke=DARK, sw=1.5)
    s.line(px + 16 + 44 * (pw - 32) / 59, yy + 355, px + 16 + 44 * (pw - 32) / 59, yy + 495,
           stroke=SEV["invalid"]["stroke"], dash="4 3")
    s.text(px + 16 + 44 * (pw - 32) / 59 + 4, yy + 368, "INVALID from here", 10.5, fill=SEV["invalid"]["txt"])
    s.button(px + 16, yy + 520, 186, 32, "Extraction page \u203A")
    s.button(px + 218, yy + 520, 186, 32, "Expert tab \u203A")
    s.text(16, 660, "Click any element of the synoptic: the panel on the right shows its controls, a short trend "
           "and its expert data.", 13, fill=DARK)
    s.text(16, 680, "The subsystem tabs show the same panel next to a larger drawing of that subsystem.", 13, fill=DARK)
    s.trend(16, 700, 556, 184, "Extraction voltages", [("Source", [0.75] * 60), ("Puller", [0.21] * 60),
            ("Lens 1", [0.30] * 60)], "kV", ["0", "10", "20"])
    s.trend(588, 700, 560, 184, "Faraday cup current", [("FC current", [0.85 + 0.01 * math.sin(j / 3)
            for j in range(60)])], "mA", ["0", "0.5", "1.0"])
    return s.save()


def vac_schematic(s, x0, y0, sel=None, big=True):
    """Vacuum and gas drawing for option B, about 1130 x 490."""
    s.rect(x0, y0, 1132, 492, fill=PANEL, stroke=LINE, rx=4)
    s.text(x0 + 12, y0 + 20, "Vacuum and gas", 13, weight="bold", fill=DARK)
    X = lambda v: x0 + v
    Y = lambda v: y0 + v
    # source, vessel, diag box
    s.rect(X(40), Y(100), 170, 110, fill="#f7f7f7", stroke=DARK, sw=1.5, dash="8 4", rx=6)
    s.text(X(125), Y(150), "Source", 12, weight="bold", anchor="middle", fill=DARK)
    s.text(X(125), Y(168), "(HV platform)", 11, anchor="middle", fill=MUTED)
    s.rect(X(260), Y(100), 320, 110, fill="#eeeeee", stroke=DARK, sw=2, rx=6)
    s.text(X(420), Y(160), "Extraction vessel", 12, weight="bold", anchor="middle", fill=DARK)
    s.rect(X(640), Y(90), 230, 130, fill="#eeeeee", stroke=DARK, sw=2, rx=6)
    s.text(X(652), Y(110), "Diagnostic box", 12, weight="bold", fill=DARK)
    s.line(X(210), Y(155), X(260), Y(155), stroke="#9e9e9e", sw=5)
    s.line(X(580), Y(155), X(640), Y(155), stroke="#9e9e9e", sw=5)
    # FC actuator
    s.path(f"M{X(820)},{Y(140)} h22 v36 h-22", stroke="#000", sw=3)
    s.line(X(831), Y(90), X(831), Y(140), stroke="#000", sw=2)
    s.tag(X(890), Y(176), 190, "Valve 4  Faraday cup", [("actuator", "IN", "ok")], selected=sel == "v4")
    s.line(X(890), Y(196), X(842), Y(160), stroke=DARK, dash="2 2")
    # gauges
    gauge(s, X(520), Y(91))
    s.tag(X(440), Y(18), 170, "Source gauge (nAIM)", [("p", "2.4e-6 Torr", "ok"), ("gauge", "ON", "ok")],
          selected=sel == "naim")
    gauge(s, X(670), Y(81))
    s.tag(X(640), Y(26), 160, "Diag. box gauge", [("p", "8.1e-7 Torr", "ok")], selected=sel == "diag")
    # turbos
    for k, px in enumerate([520, 800]):
        s.line(X(px), Y(210 if k == 0 else 220), X(px), Y(284), stroke=DARK, sw=2)
        pump(s, X(px), Y(300))
        s.line(X(px), Y(316), X(px), Y(410), stroke=DARK, sw=2)
        s.tag(X(px + 26), Y(270), 180, f"Turbo {k+1}", [("state", "NORMAL", "ok"),
              ("speed", "1200 Hz", "ok"), ("current", "0.9" + ("2" if k == 0 else "0") + " A", "ok")],
              lamp="on", selected=sel == f"tp{k+1}")
    # foreline
    s.line(X(800), Y(410), X(300), Y(410), stroke=DARK, sw=2)
    valve(s, X(640), Y(410), "h", closed=False)
    s.text(X(640), Y(440), "valve 1  foreline", 11, anchor="middle", fill=DARK)
    s.text(X(640), Y(456), "OPEN", 11, weight="bold", anchor="middle")
    if sel == "v1":
        s.rect(X(620), Y(394), 40, 32, fill="none", stroke="#000", sw=3, rx=6)
    gauge(s, X(450), Y(410))
    s.tag(X(395), Y(430), 120, "Foreline (APG)", [("p", "3.2e-2 Torr", "ok")], size=10.5, selected=sel == "apg")
    pump(s, X(300), Y(410), rough=True)
    s.text(X(300), Y(445), "Roughing pump", 11, anchor="middle", fill=MUTED)
    s.text(X(300), Y(460), "(no PVs yet)", 11, anchor="middle", fill=MUTED)
    # vent
    s.line(X(300), Y(210), X(300), Y(290), stroke=DARK, sw=2)
    valve(s, X(300), Y(290), "v", closed=True)
    s.text(X(316), Y(295), "valve 3  vent  CLOSED", 11, fill=DARK)
    # gas
    s.line(X(80), Y(210), X(80), Y(380), stroke=DARK, sw=2)
    valve(s, X(80), Y(300), "v", closed=False)
    s.text(X(96), Y(305), "valve 2  MFC shutoff  OPEN", 11, fill=DARK)
    s.tag(X(30), Y(380), 170, "Gas (MFC)", [("set", "1.20 sccm", "ok"), ("flow", "1.19 sccm", "ok")],
          selected=sel == "mfc")
    # spare channels
    s.rect(X(890), Y(26), 222, 136, fill=PANEL, stroke=LINE, rx=4)
    s.text(X(902), Y(46), "Valve box: unassigned channels", 11, weight="bold", fill=DARK)
    for i in range(4):
        s.text(X(902), Y(72 + i * 24), f"channel {5 + i}", 11, fill=MUTED)
        s.text(X(1100), Y(72 + i * 24), "CLOSED", 11, anchor="end", weight="bold", fill=DARK)


def b_vacuum():
    s = Svg("B2_vacuum", "Option B \u00B7 Synoptic with detail panel \u2014 Vacuum & gas tab (foreline valve clicked)")
    appbar(s, TABS, "Vacuum & gas")
    status_strip(s)
    vac_schematic(s, 16, 112, sel="v1")
    import math
    s.trend(16, 620, 560, 264, "Pressures (log scale)",
            [("nAIM", [0.30 + 0.004 * math.sin(j) for j in range(60)]),
             ("Diag. box", [0.24 + 0.004 * math.sin(j + 1) for j in range(60)]),
             ("APG", [0.81] * 60)], "Torr", ["1e-8", "1e-6", "1e-4", "1e-2", "1e0"])
    s.trend(592, 620, 556, 264, "Turbo speed", [("Turbo 1", [0.75] * 60), ("Turbo 2", [0.74] * 60)],
            "Hz", ["0", "400", "800", "1200", "1600"])
    px, pw = 1164, 420
    panel(s, px, 112, pw, 772, "Valve 1  foreline", "Valve box channel 1 \u00B7 VALVE:s1:set / VALVE:s1:get",
          ["Controls", "Trend", "Expert"], "Controls")
    yy = 214
    s.text(px + 16, yy, "Command", 12, weight="bold")
    s.button(px + 16, yy + 12, 186, 40, "OPEN", kind="filled", size=14)
    s.button(px + 218, yy + 12, 186, 40, "CLOSE", size=14)
    s.field(px + 16, yy + 80, 388, "read-back (valve box)", "OPEN", "")
    s.text(px + 16, yy + 150, "Context for this valve (from the registry)", 12, weight="bold")
    ctx = [("Foreline (APG)", "3.2e-2 Torr"), ("Turbo 1", "NORMAL, 1200 Hz"), ("Turbo 2", "NORMAL, 1200 Hz"),
           ("Roughing pump", "no PVs yet"), ("Vent valve 3", "CLOSED")]
    for i, (k, v) in enumerate(ctx):
        s.line(px + 16, yy + 162 + i * 28, px + pw - 16, yy + 162 + i * 28, stroke="#eeeeee")
        s.text(px + 16, yy + 180 + i * 28, k, 12, fill=MUTED)
        s.text(px + pw - 16, yy + 180 + i * 28, v, 12, weight="bold", anchor="end")
    s.text(px + 16, yy + 334, "Last changes (event log, WP9)", 12, weight="bold")
    s.rect(px + 16, yy + 344, pw - 32, 96, fill="none", stroke=MUTED, dash="4 3", rx=4)
    s.text(px + 28, yy + 368, "13:40:12  OPEN   by operator", 11.5, fill=MUTED)
    s.text(px + 28, yy + 388, "09:02:55  CLOSE  by operator", 11.5, fill=MUTED)
    s.text(px + 28, yy + 420, "placeholder until the archiver exists", 11, italic=True, fill=MUTED)
    s.text(px + 16, yy + 476, "No interlock acts on this valve today. The", 11.5, fill=MUTED)
    s.text(px + 16, yy + 494, "new interlock system may add one later.", 11.5, fill=MUTED)
    s.button(px + 16, yy + 520, 186, 32, "Expert tab \u203A")
    return s.save()


def b_expert():
    s = Svg("B3_expert", "Option B \u00B7 Synoptic with detail panel \u2014 Expert tab of the panel (Lens 2), "
            "panel widened with \u2922")
    appbar(s, TABS, "Overview")
    status_strip(s)
    synoptic(s, 16, 112, 0.70, "reads", selected="au5")
    s.text(16, 530, "The synoptic stays visible and live while the", 13, fill=DARK)
    s.text(16, 548, "expert data is open. \u2922 widens the panel to", 13, fill=DARK)
    s.text(16, 566, "two thirds of the screen, \u00D7 closes it.", 13, fill=DARK)
    s.text(16, 600, "Right-click any value: RAS context menu", 13, fill=DARK)
    s.text(16, 618, "(copy PV name, Probe).", 13, fill=DARK)
    px, pw = 868, 716
    panel(s, px, 112, pw, 772, "Lens 2  (AU 5)", "Matsusada AU20N7.5 \u00B7 Rack IOC (sim) \u00B7 chain mat_co "
          "(CO-U32), unit 5", ["Controls", "Trend", "Expert"], "Expert")
    lens2_diagnosis(s, px + 12, 202, pw - 24, compact=True)
    cols = [("PV", 268), ("value", 70), ("SEVR", 100), ("STAT", 96), ("time", 80)]
    pv_table(s, px + 12, 330, pw - 24, expert_rows_lens2(), cols, rh=24, size=11.5)
    yy = 330 + 24 * 13 + 18
    info = [("other units on chain", "Lens 1 OK, Lens 3 not polled"), ("last good reply", "14:02:11"),
            ("poll rate (measured)", "monitors 6.4 Hz, status 1 Hz")]
    for i, (k, v) in enumerate(info):
        s.text(px + 16, yy + i * 22, k, 12, fill=MUTED)
        s.text(px + 200, yy + i * 22, v, 12, weight="bold")
    s.button(px + 16, yy + 76, 200, 32, "Copy all PV names")
    s.button(px + 232, yy + 76, 200, 32, "Open in Probe")
    s.button(px + 448, yy + 76, 200, 32, "Inject fault \u2026 (sim)", kind="ghost")
    return s.save()


# ============================================================================ option C
RAIL = [("Overview", "ok"), ("Plasma generator", "minor"), ("Extraction", "invalid"), ("Vacuum & gas", "ok"),
        ("Cooling & interlocks", "ok"), ("Diagnostics", "ok"), ("Trends", None), ("Infrastructure", "ok")]


def rail(s, active):
    s.rect(0, 100, 200, 800, fill="#e4e4e4", stroke="none")
    s.line(200, 100, 200, 900, stroke=LINE)
    y = 128
    for i, (t, sev) in enumerate(RAIL):
        if t == "Trends":
            s.line(12, y - 18, 188, y - 18, stroke=LINE)
        if t == active:
            s.rect(0, y - 20, 200, 36, fill=PANEL, stroke="none")
            s.rect(0, y - 20, 5, 36, fill=DARK, stroke="none")
        s.text(18, y + 3, t, 13, weight="bold" if t == active else "normal")
        if sev:
            st = {"ok": "on", "minor": "minor", "invalid": "invalid"}[sev]
            if sev == "ok":
                s.circle(184, y - 2, 5, fill="#bdbdbd", stroke="#9e9e9e")
            else:
                s.lamp(184, y - 2, st, r=6)
        y += 44
    s.text(14, 500, "Dot = worst severity", 11, fill=MUTED)
    s.text(14, 516, "on that page", 11, fill=MUTED)


def c_overview():
    s = Svg("C1_overview", "Option C \u00B7 Side rail, tables and expert mode \u2014 Overview "
            "(subsystem tiles over a compact synoptic)")
    appbar(s, None, None, expert=False)
    status_strip(s)
    rail(s, "Overview")
    tiles = [("Plasma generator", "minor", [("Filament", "182.4 A", "ok"), ("Discharge", "7.98 A  92.1 V", "ok"),
                                            ("Magnet plate", "62.3 \u00B0C", "minor")]),
             ("Extraction", "invalid", [("Source", "15.00 kV  1.20 mA", "ok"), ("Puller", "4.20 kV  0.35 mA", "ok"),
                                        ("Lens 2", "", "invalid")]),
             ("Vacuum & gas", "ok", [("Source p", "2.4e-6 Torr", "ok"), ("Turbos", "2 \u00D7 NORMAL", "ok"),
                                     ("Gas", "1.19 sccm", "ok")]),
             ("Cooling & interlocks", "ok", [("Doors", "closed, permit", "ok"), ("Front plate", "1.21 l/min", "ok"),
                                             ("Water max", "31.2 \u00B0C", "ok")]),
             ("Diagnostics", "ok", [("Faraday cup", "0.85 mA", "ok"), ("Cup", "IN", "ok"),
                                    ("Diag. box p", "8.1e-7 Torr", "ok")])]
    tw_ = (1368 - 4 * 12) / 5
    for i, (t, sev, rows) in enumerate(tiles):
        x = 216 + i * (tw_ + 12)
        s.rect(x, 116, tw_, 156, fill=PANEL, stroke=SEV[sev]["stroke"] if sev != "ok" else LINE,
               sw=SEV[sev]["sw"] if sev != "ok" else 1, rx=6)
        if sev != "ok":
            s.rect(x, 116, tw_, 30, fill=SEV[sev]["fill"], stroke="none", rx=6)
        s.text(x + 12, 137, t, 14, weight="bold")
        s.text(x + tw_ - 12, 137, {"ok": "OK", "minor": "MINOR", "invalid": "INVALID"}[sev], 11, weight="bold",
               anchor="end", fill=SEV[sev]["txt"] if sev != "ok" else MUTED)
        for j, (k, v, rs) in enumerate(rows):
            yy = 160 + j * 30
            if rs != "ok":
                s.rect(x + 6, yy - 2, tw_ - 12, 26, fill=SEV[rs]["fill"], stroke=SEV[rs]["stroke"], rx=3)
            s.text(x + 12, yy + 16, k, 12, fill=MUTED if rs == "ok" else SEV[rs]["txt"])
            vv = "INVALID" if rs == "invalid" else v + ("  \u25B2" if rs == "minor" else "")
            s.text(x + tw_ - 12, yy + 16, vv, 13, weight="bold", anchor="end",
                   fill=TXT if rs == "ok" else SEV[rs]["txt"])
        s.text(x + tw_ - 12, 266, "open \u203A", 11, anchor="end", fill=DARK)
    synoptic(s, 216 + (1368 - 1200 * 1.0) / 2, 300, 1.0, "reads")
    s.text(216, 880, "Tiles say where to look; the synoptic says where it is on the machine. Click a tile, "
           "a tag or a rail entry to open the page.", 13, fill=DARK)
    return s.save()


def c_table(s, x, y, cols, rows, rh=30):
    """rows: ('group', text) or list of cells. cell: str | ('val', text, sev) | ('btn', label, on) | ('in', text)
    | ('lamp', state, text)"""
    w = sum(c[1] for c in cols)
    s.rect(x, y, w, rh, fill=LIGHT, stroke="none")
    cx = x
    for t, cw in cols:
        s.text(cx + 10, y + rh - 10, t, 12, weight="bold", fill=DARK)
        cx += cw
    yy = y + rh
    for r in rows:
        if r[0] == "group":
            s.rect(x, yy, w, rh, fill="#f0f0f0", stroke="none")
            s.text(x + 10, yy + rh - 10, r[1], 13, weight="bold")
            if len(r) > 2:
                s.text(x + w - 10, yy + rh - 10, r[2], 11, anchor="end", fill=MUTED)
            yy += rh
            continue
        rowsev = next((c[2] for c in r if isinstance(c, tuple) and c[0] == "val" and c[2] != "ok"), "ok")
        if rowsev != "ok":
            s.rect(x, yy, w, rh, fill=SEV[rowsev]["fill"], stroke="none")
            s.rect(x, yy, 4, rh, fill=SEV[rowsev]["stroke"], stroke="none")
        s.rect(x, yy, w, rh, fill="none", stroke="#e6e6e6")
        cx = x
        for (t, cw), c in zip(cols, r):
            if isinstance(c, str):
                mono = t in ("PV", "PV name")
                if mono:
                    s.raw(f'<text x="{cx + 10}" y="{yy + rh - 10}" font-size="11.5" '
                          f'font-family="DejaVu Sans Mono, monospace" fill="{DARK}">{escape(c)}</text>')
                else:
                    s.text(cx + 10, yy + rh - 10, c, 12.5, fill=TXT if c else MUTED)
            elif c[0] == "val":
                sv = c[2]
                txt = "INVALID" if sv == "invalid" else c[1] + ("  " + SEV[sv]["mark"] if sv == "minor" else "")
                s.text(cx + 10, yy + rh - 10, txt, 13, weight="bold", fill=SEV[sv]["txt"] if sv != "ok" else TXT)
            elif c[0] == "btn":
                s.rect(cx + 8, yy + 4, 92, rh - 8, fill=DARK if c[2] else PANEL, stroke=DARK, rx=4)
                s.text(cx + 54, yy + rh - 10, c[1], 11.5, weight="bold", anchor="middle",
                       fill=PANEL if c[2] else DARK)
            elif c[0] == "in":
                s.rect(cx + 8, yy + 4, cw - 24, rh - 8, fill="#fafafa", stroke=DARK, rx=3)
                s.text(cx + 14, yy + rh - 10, c[1] + "  \u270E", 12.5)
            elif c[0] == "lamp":
                s.lamp(cx + 18, yy + rh / 2, c[1], r=5)
                s.text(cx + 30, yy + rh - 10, c[2], 12.5,
                       fill=SEV["invalid"]["txt"] if c[1] == "invalid" else TXT)
            cx += cw
        yy += rh
    return yy


def c_vacuum():
    s = Svg("C2_vacuum", "Option C \u00B7 Side rail, tables and expert mode \u2014 Vacuum & gas page "
            "(one row per channel, trends on the right)")
    appbar(s, None, None, expert=False)
    status_strip(s)
    rail(s, "Vacuum & gas")
    s.text(216, 128, "Vacuum & gas", 18, weight="bold")
    s.text(380, 128, "one row per channel \u00B7 click a name for its trend \u00B7 right-click: PV name, Probe",
           12, fill=MUTED)
    cols = [("Channel", 230), ("Command / set point", 200), ("Read-back", 190), ("State", 180), ("Note", 70)]
    V, B = (lambda t, sv="ok": ("val", t, sv)), (lambda t, on: ("btn", t, on))
    rows = [("group", "Pressures"),
            ["Source (nAIM)", B("GAUGE ON", True), V("2.4e-6 Torr"), ("lamp", "on", "gauge on"), ""],
            ["Diagnostic box", "", V("8.1e-7 Torr"), "", ""],
            ["Foreline (APG)", "", V("3.2e-2 Torr"), "", ""],
            ("group", "Turbopumps (NT 20)"),
            ["Turbo 1", B("RUN", True), V("1200 Hz  0.92 A"), ("lamp", "on", "NORMAL"), "3 s"],
            ["Turbo 2", B("RUN", True), V("1200 Hz  0.88 A"), ("lamp", "on", "NORMAL"), "3 s"],
            ("group", "Gas"),
            ["MFC set point / flow", ("in", "1.20 sccm"), V("1.19 sccm"), "", ""],
            ("group", "Valves", "valve box, 8 channels"),
            ["1  Foreline", B("OPEN", True), V("OPEN"), "", ""],
            ["2  MFC shutoff", B("OPEN", True), V("OPEN"), "", ""],
            ["3  Vent", B("CLOSED", False), V("CLOSED"), "", ""],
            ["4  Faraday cup actuator", B("IN", True), V("IN"), "", ""],
            ["5 \u2013 8  spare", "", V("all CLOSED"), "", ""],
            ("group", "Roughing pump"),
            ["(no PVs yet)", "", "", "", ""]]
    c_table(s, 216, 146, cols, rows)
    import math
    s.trend(1104, 146, 480, 360, "Pressures (log scale)",
            [("nAIM", [0.30 + 0.004 * math.sin(j) for j in range(60)]),
             ("Diag. box", [0.24 + 0.004 * math.sin(j + 1) for j in range(60)]),
             ("APG", [0.81] * 60)], "Torr", ["1e-8", "1e-6", "1e-4", "1e-2", "1e0"])
    s.trend(1104, 524, 480, 360, "Turbo speed", [("Turbo 1", [0.75] * 60), ("Turbo 2", [0.74] * 60)],
            "Hz", ["0", "400", "800", "1200", "1600"])
    s.text(216, 870, "Note column: record age of the turbo RS-232 data. Expert mode (top bar) adds PV, SEVR/STAT "
           "and time columns to this same table.", 12, fill=DARK)
    return s.save()


def c_expert():
    s = Svg("C3_expert", "Option C \u00B7 Side rail, tables and expert mode \u2014 Extraction page with "
            "Expert ON (extra columns, device rows)")
    appbar(s, None, None, expert=True)
    status_strip(s)
    rail(s, "Extraction")
    s.text(216, 128, "Extraction", 18, weight="bold")
    s.text(330, 128, "Expert mode adds the columns PV, SEVR / STAT, updated and a header row per device. "
           "Stays on until switched off.", 12, fill=MUTED)
    cols = [("Channel", 150), ("Set / command", 130), ("Read-back", 130), ("PV", 300), ("SEVR / STAT", 160),
            ("updated", 90)]
    V = lambda t, sv="ok": ("val", t, sv)
    rows = [("group", "Ion source voltage (AU 1)", "AU20P15 \u00B7 mat_opt (USB-OPT) unit 1 \u00B7 6.6 Hz"),
            ["voltage", ("in", "15.00 kV"), V("15.00 kV"), "AU-20P7-1:voltage:read", "NO_ALARM", "14:04:25"],
            ["current", "", V("1.20 mA"), "AU-20P7-1:current:read", "NO_ALARM", "14:04:25"],
            ("group", "Puller (AU 2)", "AU20N7.5 \u00B7 mat_opt unit 2 \u00B7 6.6 Hz"),
            ["voltage", ("in", "4.20 kV"), V("4.20 kV"), "AU-20P7-2:voltage:read", "NO_ALARM", "14:04:25"],
            ("group", "Lens 1 (AU 3)", "AU20P7.5 \u00B7 mat_co (CO-U32) unit 3 \u00B7 6.4 Hz"),
            ["voltage", ("in", "6.00 kV"), V("6.00 kV"), "AU-20P7-3:voltage:read", "NO_ALARM", "14:04:25"],
            ("group", "Lens 2 (AU 5)", "AU20N7.5 \u00B7 mat_co unit 5 \u00B7 last reply 14:02:11"),
            ["voltage set", ("in", "2.50 kV"), "", "AU-20P7-5:voltage:setpoint", "NO_ALARM", "14:01:40"],
            ["voltage", "", V("", "invalid"), "AU-20P7-5:voltage:read", "INVALID / TIMEOUT", "14:02:11"],
            ["current", "", V("", "invalid"), "AU-20P7-5:current:read", "INVALID / TIMEOUT", "14:02:11"],
            ["output", ("btn", "ON", True), V("", "invalid"), "AU-20P7-5:read_output_status", "INVALID / TIMEOUT",
             "14:02:11"],
            ["status word", "", V("", "invalid"), "AU-20P7-5:status:read", "INVALID / TIMEOUT", "14:02:11"],
            ("group", "Lens 3 (AU 4)", "not polled (scan off by macro)"),
            ["voltage", "", "", "AU-20P7-4:voltage:read", "scan off", ""],
            ("group", "Commands"),
            ["all HV off", ("btn", "ALL OFF", False), "", "AU:alloff:set", "NO_ALARM", ""]]
    c_table(s, 216, 146, cols, rows, rh=29)
    s.trend(1194, 146, 390, 556, "Extraction voltages", [("Source", [0.75] * 60), ("Puller", [0.21] * 60),
            ("Lens 1", [0.30] * 60), ("Lens 2", [0.125] * 44)], "kV", ["0", "5", "10", "15", "20"])
    lens2_diagnosis(s, 216, 724, 960)
    s.card(1194, 724, 390, 152, "Infrastructure (rail entry)")
    for i, (k, v) in enumerate([("Rack IOC", "mode sim, heartbeat 1 s"), ("HV IOC", "mode sim, heartbeat 1 s"),
                                ("libcom1 devices", "id, firmware, channels"), ("simulator", "fault injection")]):
        s.text(1210, 754 + i * 28, k, 12, fill=MUTED)
        s.text(1340, 754 + i * 28, v, 12, weight="bold")
    return s.save()


# ============================================================================ shared
def shared():
    s = Svg("S1_widgets_and_severity", "Shared by all options \u2014 alarm severity, emulator banner, "
            "widget classes")
    y = 60
    s.text(16, y, "1  How a value shows its EPICS alarm severity (same rule for fields, synoptic tags, table rows, "
           "lamps)", 15, weight="bold")
    states = [("NO_ALARM", "ok", "plain, no colour"), ("MINOR", "minor", "amber fill + \u25B2"),
              ("MAJOR", "major", "red fill + \u25A0"), ("INVALID", "invalid", "purple, value hidden"),
              ("disconnected", "disc", "grey dashed, \u00D7")]
    for i, (n, sv, note) in enumerate(states):
        x = 16 + i * 316
        s.text(x, y + 30, n, 13, weight="bold", fill=SEV[sv]["txt"] if sv != "ok" else TXT)
        s.text(x + 300, y + 30, note, 11, anchor="end", fill=MUTED)
        s.field(x, y + 48, 200, "Puller voltage read", "4.20", "kV", sev=sv)
        s.lamp(x + 230, y + 66, {"ok": "on", "minor": "minor", "major": "fault", "invalid": "invalid",
                                 "disc": "disc"}[sv], r=8)
        s.tag(x, y + 100, 200, "Puller (AU 2)", [("U", "4.20 kV", sv),
              ("I", "0.35 mA", sv if sv in ("invalid", "disc") else "ok")],
              sev=sv if sv in ("invalid", "disc") else "ok")
    s.text(16, y + 192, "INVALID (device silent, record cannot be trusted): the number is replaced by the word "
           "INVALID; the last good value and its time are one click away (expert).", 12, fill=DARK)
    s.text(16, y + 210, "Disconnected (no Channel Access connection, IOC down): RAS already replaces the value by "
           "the PV name and a disconnect icon; we show \u2018no connection\u2019 and grey it out.", 12, fill=DARK)
    s.text(16, y + 228, "Colour is never the only carrier: the marker (\u25B2 \u25A0 ? \u00D7) and the word "
           "keep it readable in grayscale and for colour-blind readers. No thresholds are coded in pages.",
           12, fill=DARK)
    y = 318
    s.text(16, y, "2  Emulator banner (on every page, below the app bar)", 15, weight="bold")
    s.rect(16, y + 14, 1568, 28, fill="url(#hatchc)", stroke="none")
    s.rect(24, y + 17, 640, 22, fill="#0b2e6b", stroke="none", rx=3)
    s.text(32, y + 33, "EMULATOR \u2014 rack IOC and HV IOC report mode sim. No hardware is connected.",
           12.5, weight="bold", fill=PANEL)
    s.rect(16, y + 50, 1568, 28, fill="url(#hatchc)", stroke="none")
    s.rect(24, y + 53, 760, 22, fill="#0b2e6b", stroke="none", rx=3)
    s.text(32, y + 69, "MIXED \u2014 rack IOC in mode sim, HV IOC on real hardware. Platform values are real.",
           12.5, weight="bold", fill=PANEL)
    s.text(16, y + 98, "Blue diagonal stripes: a colour no alarm uses. Mode comes from each IOC\u2019s mode PV, "
           "not from a GUI setting. Mode unknown (PV disconnected) shows the banner too. Window title gets "
           "the prefix \u2018[SIM]\u2019.", 12, fill=DARK)
    y = 446
    s.text(16, y, "3  Widget classes (one React component each, PV names from the registry)", 15, weight="bold")
    # supply
    s.card(16, y + 20, 380, 176, "Supply: Puller (AU 2)", link="expert \u203A")
    s.field(30, y + 50, 170, "voltage set", "4.20", "kV", inp=True)
    s.field(212, y + 50, 170, "current limit set", "0.50", "mA", inp=True)
    s.field(30, y + 100, 170, "voltage read", "4.20", "kV")
    s.field(212, y + 100, 170, "current read", "0.35", "mA")
    s.toggle(30, y + 150, 110, True, "OUTPUT ON", "OUTPUT OFF")
    s.lamp(156, y + 165, "on")
    s.text(168, y + 169, "output on (read-back)", 11, fill=MUTED)
    # valve
    s.card(412, y + 20, 180, 176, "Valve: 1 Foreline")
    s.toggle(428, y + 56, 148, True, "OPEN", "CLOSED")
    s.lamp(436, y + 112, "on")
    s.text(448, y + 116, "read-back OPEN", 11, fill=MUTED)
    valve(s, 502, y + 152, "h", closed=False)
    s.text(502, y + 184, "synoptic symbol", 10.5, anchor="middle", fill=MUTED)
    # gauge
    s.card(608, y + 20, 200, 176, "Gauge: nAIM")
    s.field(624, y + 54, 168, "pressure", "2.4e-6", "Torr")
    s.toggle(624, y + 108, 80, True, "ON", "OFF")
    s.text(712, y + 128, "enable (if any)", 10.5, fill=MUTED)
    gauge(s, 700, y + 168)
    # turbo
    s.card(824, y + 20, 250, 176, "Turbo pump: Turbo 1")
    s.toggle(840, y + 52, 80, True, "RUN", "STOP")
    for j, (lab, st) in enumerate([("accel.", "off"), ("normal", "on"), ("failure", "off")]):
        s.lamp(948 + j * 46, y + 64, st)
        s.text(948 + j * 46, y + 86, lab, 10, anchor="middle", fill=MUTED)
    s.field(840, y + 108, 110, "speed", "1200", "Hz")
    s.field(960, y + 108, 98, "current", "0.92", "A")
    s.text(840, y + 172, "state NORMAL \u00B7 record age 3 s", 11, fill=MUTED)
    # mfc
    s.card(1090, y + 20, 200, 176, "Mass flow controller")
    s.field(1106, y + 52, 168, "set point", "1.20", "sccm", inp=True)
    s.field(1106, y + 104, 168, "flow", "1.19", "sccm")
    s.text(1106, y + 170, "wink: expert only", 11, fill=MUTED)
    # reading
    s.card(1306, y + 20, 278, 176, "Reading (T, flow, I)")
    s.field(1322, y + 52, 120, "Back plate", "41.2", "\u00B0C")
    s.field(1452, y + 52, 118, "Magnet plate", "62.3", "\u00B0C", sev="minor")
    s.field(1322, y + 104, 120, "Front plate", "1.21", "l/min")
    s.field(1452, y + 104, 118, "Faraday cup", "0.85", "mA")
    s.text(1322, y + 170, "one class, unit and format from the PV", 10.5, fill=MUTED)
    y2 = y + 214
    s.card(16, y2, 380, 120, "Interlock (old box)")
    for j, (lab, st) in enumerate([("HV door lower", "on"), ("HV door upper", "on"), ("permit HV and discharge", "on")]):
        s.lamp(36, y2 + 32 + j * 28, st)
        s.text(50, y2 + 36 + j * 28, lab, 12)
        s.text(380, y2 + 36 + j * 28, "closed" if j < 2 else "yes", 12, weight="bold", anchor="end")
    s.card(412, y2, 396, 120, "IOC status chip (app bar)")
    s.rect(428, y2 + 30, 190, 22, fill=PANEL, stroke=DARK, rx=11)
    s.lamp(441, y2 + 41, "on", r=4.5)
    s.text(450, y2 + 46, "Rack IOC  sim  \u2665 1 s", 11.5)
    s.rect(428, y2 + 62, 190, 22, fill=SEV["major"]["fill"], stroke=SEV["major"]["stroke"], sw=2, rx=11)
    s.lamp(441, y2 + 73, "fault", r=4.5)
    s.text(450, y2 + 78, "HV IOC  heartbeat lost", 11.5, fill=SEV["major"]["txt"])
    s.text(630, y2 + 46, "heartbeat + mode PV", 11, fill=MUTED)
    s.text(630, y2 + 78, "no beat for 5 s: MAJOR", 11, fill=MUTED)
    s.card(824, y2, 466, 120, "Device identity and communication (expert)")
    for j, (k, v) in enumerate([("id / firmware", "VALVE \u00B7 libcom1 p2 2026-11-03"),
                                ("channels", "s1 s2 s3 s4 s5 s6 s7 s8"), ("last reply", "0.4 s ago")]):
        s.text(840, y2 + 36 + j * 26, k, 12, fill=MUTED)
        s.text(980, y2 + 36 + j * 26, v, 12, weight="bold")
    s.card(1306, y2, 278, 120, "Command with confirm")
    s.rect(1322, y2 + 30, 160, 34, fill="#fafafa", stroke="#000", sw=2.5, rx=4)
    s.text(1402, y2 + 52, "ALL HV OFF", 13, weight="bold", anchor="middle")
    s.text(1322, y2 + 88, "one click, no confirm (safe direction)", 10.5, fill=MUTED)
    s.text(1322, y2 + 106, "unsafe direction: confirm dialog", 10.5, fill=MUTED)
    s.text(16, 884, "Plus: Trend (RAS GraphY with time stamps), synoptic symbols (electrode, valve, gauge, pump, "
           "cup) and the value tag. Placeholders in the app bar: PDF report (WP8); loops (WP10) get their own "
           "widget class later.", 12, fill=DARK)
    return s.save()


def main():
    for f in [a_overview, a_vacuum, a_expert, b_overview, b_vacuum, b_expert, c_overview, c_vacuum,
              c_expert, shared]:
        print(f())


if __name__ == "__main__":
    main()
