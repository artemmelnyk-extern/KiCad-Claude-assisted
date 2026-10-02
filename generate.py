#!/usr/bin/env python3
"""Generate pc817_bench.kicad_sch (KiCad 7 format, opens in 7/8/9).

Two identical 24 V input channels for a board with the Arduino UNO shield header
(UNO R4 WiFi: 5 V logic, UNO Q: 3.3 V logic):
  IN -> 2 x 2.2k 1/4W in series -> indicator LED -> PC817 LED -> GND24
  1N4148 reversed across both LEDs (cathode after the resistor)
  PC817 collector -> Dx with 10k pull-up to IOREF, emitter -> Arduino GND
All symbols are embedded (library "bench"), so no KiCad library is needed.
Run: python3 generate.py   (writes into ./kicad)
"""
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent / "kicad"

ROOT = "6f1d2c1e-0a4b-4c55-9a51-2b8f0c817001"
PROJECT = "pc817_bench"
_n = [0]


def uid():
    _n[0] += 1
    return str(uuid.uuid5(uuid.UUID(ROOT), "item%d" % _n[0]))


FONT = "(effects (font (size 1.27 1.27)))"


def pin(num, name, x, y, ang, length=1.27):
    return ('(pin passive line (at %g %g %d) (length %g) (name "%s" %s) (number "%s" %s))'
            % (x, y, ang, length, name, FONT, num, FONT))


def libsym(name, ref, graphics, pins, hide_names=True, name_offset=0, hide_numbers=False):
    hide = "(pin_names (offset %g) hide)" % name_offset if hide_names else "(pin_names (offset %g))" % name_offset
    if hide_numbers:
        hide = "(pin_numbers hide) " + hide
    return """(symbol "bench:%s" %s (in_bom yes) (on_board yes)
      (property "Reference" "%s" (at 0 0 0) %s)
      (property "Value" "%s" (at 0 0 0) %s)
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "%s_0_1" %s)
      (symbol "%s_1_1" %s))""" % (name, hide, ref, FONT, name, FONT, name, " ".join(graphics), name, " ".join(pins))


def rect(x1, y1, x2, y2, fill="none"):
    return ("(rectangle (start %g %g) (end %g %g) (stroke (width 0.254) (type default)) (fill (type %s)))"
            % (x1, y1, x2, y2, fill))


def poly(pts, fill="none"):
    return ("(polyline (pts %s) (stroke (width 0.254) (type default)) (fill (type %s)))"
            % (" ".join("(xy %g %g)" % p for p in pts), fill))


# symbol name -> {pin number: (x, y)} in library coordinates (y up)
PINS = {
    "R_H": {"1": (-3.81, 0), "2": (3.81, 0)},
    "R_V": {"1": (0, 3.81), "2": (0, -3.81)},
    "LED_H": {"2": (-3.81, 0), "1": (3.81, 0)},          # 2 = anode (left), 1 = cathode (right)
    "D_V": {"1": (0, 3.81), "2": (0, -3.81)},            # 1 = cathode (top), 2 = anode (bottom)
    "PC817": {"1": (-7.62, 2.54), "2": (-7.62, -2.54), "4": (7.62, 2.54), "3": (7.62, -2.54)},
    "CONN6": {str(i + 1): (5.08, 6.35 - 2.54 * i) for i in range(6)},
    "FUSE_H": {"1": (-3.81, 0), "2": (3.81, 0)},
}

# Arduino UNO shield header, common to the UNO R4 WiFi and the UNO Q. Only pins present
# on every UNO-format board are drawn; "NC" is the unnamed first pin of the power header.
# Left side: power header, extra OFF/VRTC header, analog header. Right side: digital headers.
UNO_LEFT = ["NC", "IOREF", "RESET", "3V3", "5V", "GND1", "GND2", "VIN",
            "A0", "A1", "A2", "A3", "A4", "A5"]
UNO_RIGHT = ["SCL", "SDA", "AREF", "GND3", "D13", "D12", "D11", "D10", "D9", "D8",
             "D7", "D6", "D5", "D4", "D3", "D2", "D1", "D0"]
UNO_TOP = 21.59
# Pin numbers are the pad numbers of KiCad's footprint Module:Arduino_UNO_R3:
# 1..14 along the power + analog headers, 15..32 along the digital headers (D0 = 15, SCL = 32).
UNO_NUM = {n: str(i + 1) for i, n in enumerate(UNO_LEFT)}
UNO_NUM.update({n: str(32 - i) for i, n in enumerate(UNO_RIGHT)})
PINS["UNO_R4_WIFI"] = {}
for i, n in enumerate(UNO_LEFT):
    PINS["UNO_R4_WIFI"][UNO_NUM[n]] = (-15.24, UNO_TOP - 2.54 * i)
for i, n in enumerate(UNO_RIGHT):
    PINS["UNO_R4_WIFI"][UNO_NUM[n]] = (15.24, UNO_TOP - 2.54 * i)


def uno_pins():
    out = []
    for n, num in UNO_NUM.items():
        x, y = PINS["UNO_R4_WIFI"][num]
        shown = "GND" if n.startswith("GND") else n
        out.append(pin(num, shown, x, y, 0 if x < 0 else 180, 2.54))
    return out


FOOTPRINTS = {
    "R_H": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
    "R_V": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
    "LED_H": "LED_THT:LED_D3.0mm",
    "D_V": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
    "PC817": "Package_DIP:DIP-4_W7.62mm",
    "CONN6": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-6_1x06_P5.00mm_Horizontal",
    "FUSE_H": "Fuse:Fuse_Littelfuse_372_D8.50mm",
    "UNO_R4_WIFI": "Module:Arduino_UNO_R3",
}


# Terminal block, top to bottom. Each e-stop button is wired between ESn+ and ESn.
J1_PINS = ["24V_IN", "ES1+", "ES1", "ES2+", "ES2", "0V"]
J1_NETS = ["+24V_IN", "+24V", "ES1", "+24V", "ES2", "GND_24V"]

LIB = [
    libsym("R_H", "R", [rect(-2.54, -1.016, 2.54, 1.016)],
           [pin("1", "~", -3.81, 0, 0), pin("2", "~", 3.81, 0, 180)]),
    libsym("R_V", "R", [rect(-1.016, -2.54, 1.016, 2.54)],
           [pin("1", "~", 0, 3.81, 270), pin("2", "~", 0, -3.81, 90)]),
    libsym("LED_H", "D",
           [poly([(-1.27, 1.27), (-1.27, -1.27), (1.27, 0), (-1.27, 1.27)]),
            poly([(1.27, 1.27), (1.27, -1.27)]),
            poly([(-2.54, 0), (2.54, 0)]),
            poly([(0, 2.032), (1.27, 3.302)]), poly([(1.27, 2.032), (2.54, 3.302)])],
           [pin("2", "A", -3.81, 0, 0), pin("1", "K", 3.81, 0, 180)]),
    libsym("D_V", "D",
           [poly([(-1.27, -1.27), (1.27, -1.27), (0, 1.27), (-1.27, -1.27)]),
            poly([(-1.27, 1.27), (1.27, 1.27)]),
            poly([(0, -2.54), (0, 2.54)])],
           [pin("1", "K", 0, 3.81, 270), pin("2", "A", 0, -3.81, 90)]),
    libsym("PC817", "U",
           [rect(-5.08, -5.08, 5.08, 5.08, "background"),
            # LED
            poly([(-5.08, 2.54), (-2.54, 2.54), (-2.54, 1.27)]),
            poly([(-3.556, 1.27), (-1.524, 1.27), (-2.54, -0.508), (-3.556, 1.27)]),
            poly([(-3.556, -0.508), (-1.524, -0.508)]),
            poly([(-2.54, -0.508), (-2.54, -2.54), (-5.08, -2.54)]),
            # light arrows
            poly([(-0.762, 0.762), (0.508, 0.762)]), poly([(-0.762, -0.254), (0.508, -0.254)]),
            # phototransistor
            poly([(1.778, 1.524), (1.778, -1.524)]),
            poly([(1.778, 0.508), (3.81, 2.54), (5.08, 2.54)]),
            poly([(1.778, -0.508), (3.81, -2.54), (5.08, -2.54)])],
           [pin("1", "A", -7.62, 2.54, 0, 2.54), pin("2", "K", -7.62, -2.54, 0, 2.54),
            pin("4", "C", 7.62, 2.54, 180, 2.54), pin("3", "E", 7.62, -2.54, 180, 2.54)]),
    libsym("CONN6", "J", [rect(-7.62, -8.89, 2.54, 8.89, "background")],
           [pin(str(i + 1), n, 5.08, 6.35 - 2.54 * i, 180, 2.54) for i, n in enumerate(J1_PINS)],
           hide_names=False, name_offset=0.508),
    libsym("FUSE_H", "F", [rect(-2.54, -1.016, 2.54, 1.016), poly([(-2.54, 0), (2.54, 0)])],
           [pin("1", "~", -3.81, 0, 0), pin("2", "~", 3.81, 0, 180)]),
    libsym("UNO_R4_WIFI", "A", [rect(-12.7, -24.13, 12.7, 24.13, "background")], uno_pins(),
           hide_names=False, name_offset=0.508, hide_numbers=True),
]

items = []


def place(sym, ref, value, x, y, ref_dx=0.0, ref_dy=-3.81, val_dx=0.0, val_dy=3.81):
    pins = " ".join('(pin "%s" (uuid %s))' % (n, uid()) for n in PINS[sym])
    items.append("""(symbol (lib_id "bench:%s") (at %g %g 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid %s)
    (property "Reference" "%s" (at %g %g 0) %s)
    (property "Value" "%s" (at %g %g 0) %s)
    (property "Footprint" "%s" (at %g %g 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at %g %g 0) (effects (font (size 1.27 1.27)) hide))
    %s
    (instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))"""
                 % (sym, x, y, uid(), ref, x + ref_dx, y + ref_dy, FONT, value, x + val_dx, y + val_dy, FONT,
                    FOOTPRINTS[sym], x, y, x, y, pins, PROJECT, ROOT, ref))
    # schematic pin positions (y axis points down in a sheet)
    return {n: (round(x + px, 2), round(y - py, 2)) for n, (px, py) in PINS[sym].items()}


def wire(*pts):
    for a, b in zip(pts, pts[1:]):
        items.append("(wire (pts (xy %g %g) (xy %g %g)) (stroke (width 0) (type default)) (uuid %s))"
                     % (a[0], a[1], b[0], b[1], uid()))


def junction(p):
    items.append("(junction (at %g %g) (diameter 0) (color 0 0 0 0) (uuid %s))" % (p[0], p[1], uid()))


def label(name, p, right=False):
    just = "right bottom" if right else "left bottom"
    items.append('(label "%s" (at %g %g 0) (effects (font (size 1.27 1.27)) (justify %s)) (uuid %s))'
                 % (name, p[0], p[1], just, uid()))


def no_connect(p):
    items.append("(no_connect (at %g %g) (uuid %s))" % (p[0], p[1], uid()))


def text(s, x, y, size=1.27):
    items.append('(text "%s" (at %g %g 0) (effects (font (size %g %g)) (justify left bottom)) (uuid %s))'
                 % (s, x, y, size, size, uid()))


def channel(k, y):
    """One e-stop input channel on the horizontal line y. k = 1 or 2."""
    n_in, n_out = "ES%d" % k, "D%d" % (k + 1)
    ra = place("R_H", "R%d" % (2 * k - 1), "1.5k", 71.12, y, ref_dy=-5.08, val_dy=-2.54)
    rb = place("R_H", "R%d" % (2 * k), "1.5k", 81.28, y, ref_dy=-5.08, val_dy=-2.54)
    r = {"1": ra["1"], "2": rb["2"]}
    wire(ra["2"], rb["1"])
    led = place("LED_H", "D%d" % k, "LED red", 97.79, y, ref_dy=-5.08)
    dio = place("D_V", "D%d" % (k + 2), "1N4148", 88.9, y + 3.81, ref_dx=-5.08, ref_dy=-1.27, val_dx=-5.08, val_dy=1.27)
    u = place("PC817", "U%d" % k, "PC817", 119.38, y + 2.54, ref_dx=-3.81, ref_dy=-7.62, val_dx=-3.81, val_dy=7.62)
    rp = place("R_V", "R%d" % (k + 4), "10k", 137.16, y - 6.35, ref_dx=3.81, ref_dy=-1.27, val_dx=3.81, val_dy=1.27)

    gnd_y = y + 7.62
    # 24 V side
    wire((60.96, y), r["1"]); label(n_in, (60.96, y))
    wire(r["2"], led["2"]); junction(dio["1"])                 # diode cathode on the R-LED node
    wire(led["1"], u["1"])
    wire(u["2"], (109.22, u["2"][1]), (109.22, gnd_y), (60.96, gnd_y))
    junction(dio["2"]); label("GND_24V", (60.96, gnd_y))       # diode anode on the 24 V return
    # Arduino side
    wire(u["4"], (152.4, y)); junction((rp["2"][0], y)); label(n_out, (152.4, y), right=True)
    wire(rp["2"], (rp["2"][0], y))
    wire(rp["1"], (rp["1"][0], y - 12.7)); label("IOREF", (rp["1"][0], y - 12.7))
    wire(u["3"], (152.4, u["3"][1])); label("GND", (152.4, u["3"][1]), right=True)
    text("E-stop %d: button released (contact closed) -> %s LOW, LED lit" % (k, n_out), 60.96, y - 15.24)


channel(1, 71.12)
channel(2, 121.92)

# connectors
j1 = place("CONN6", "J1", "24V + e-stops", 27.94, 96.52, ref_dx=-2.54, ref_dy=-11.43, val_dx=-2.54, val_dy=11.43)
f1 = place("FUSE_H", "F1", "T2A", 46.99, j1["1"][1], ref_dx=-1.27, ref_dy=-2.54, val_dx=2.54, val_dy=-2.54)
wire(j1["1"], f1["1"])                                         # supply in -> fuse
wire(f1["2"], (f1["2"][0] + 5.08, f1["2"][1])); label("+24V", (f1["2"][0] + 5.08, f1["2"][1]), right=True)
for i, name in enumerate(J1_NETS[1:], start=2):
    p = j1[str(i)]
    end = (p[0] + 10.16, p[1])
    wire(p, end); label(name, end, right=True)
a1 = place("UNO_R4_WIFI", "A1", "UNO R4 WiFi or UNO Q", 200.66, 96.52, ref_dy=-26.67, val_dy=26.67)
UNO_NETS = {UNO_NUM[n]: net for n, net in
            {"IOREF": "IOREF", "GND1": "GND", "GND2": "GND", "D2": "D2", "D3": "D3"}.items()}
for num, p in a1.items():
    if num not in UNO_NETS:
        no_connect(p)
        continue
    left = p[0] < 200.66
    end = (p[0] - 10.16, p[1]) if left else (p[0] + 10.16, p[1])
    wire(p, end)
    label(UNO_NETS[num], end, right=not left)

text("Two e-stop inputs, 24 V loop through PC817 - shield for Arduino UNO R4 WiFi / UNO Q", 25.4, 30.48, 2.54)
text("Loop current = (24 V - 1.2 V opto - 2.0 V LED) / 3.0 k = 6.9 mA.  Each 1.5 k (1/4 W): 72 mW at 24 V, 109 mW at 28.8 V.", 25.4, 38.1)
text("Button pressed, wire cut or 24 V lost -> no current -> pin HIGH = STOP.  F1 protects the 24 V wires going out to the buttons.", 25.4, 41.91)
text("GND_24V and GND are NOT connected: this is the isolation barrier.", 25.4, 45.72)
text("Pull-ups go to IOREF: 5 V on the UNO R4 WiFi, 3.3 V on the UNO Q. Never to the 5V pin. Sketch: pinMode(D2/D3, INPUT).", 25.4, 49.53)
text("ISOLATION", 106.68, 148.59, 1.27)
items.append("(polyline (pts (xy 119.38 55.88) (xy 119.38 144.78)) (stroke (width 0.2) (type dash)) (uuid %s))" % uid())

sch = """(kicad_sch (version 20230121) (generator eeschema)
  (uuid %s)
  (paper "A4")
  (title_block (title "E-stop inputs: 24 V loop through PC817") (date "2026-10-02") (rev "0.6")
    (comment 1 "Generated by generate.py - edit the script, not this file"))
  (lib_symbols
    %s)
  %s
  (sheet_instances (path "/" (page "1")))
)
""" % (ROOT, "\n    ".join(LIB), "\n  ".join(items))

OUT.mkdir(exist_ok=True)
(OUT / "pc817_bench.kicad_sch").open("w").write(sch)
(OUT / "pc817_bench.kicad_pro").open("w").write('{\n  "meta": {\n    "filename": "pc817_bench.kicad_pro",\n    "version": 1\n  }\n}\n')
symlib = "(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n  %s\n)\n" % "\n  ".join(
    x.replace('(symbol "bench:', '(symbol "', 1) for x in LIB)
(OUT / "bench.kicad_sym").open("w").write(symlib)
(OUT / "sym-lib-table").open("w").write('(sym_lib_table\n  (version 7)\n  (lib (name "bench")(type "KiCad")(uri "${KIPRJMOD}/bench.kicad_sym")(options "")(descr "PC817 bench symbols"))\n)\n')
print("written: pc817_bench.kicad_sch, pc817_bench.kicad_pro (%d items)" % len(items))
