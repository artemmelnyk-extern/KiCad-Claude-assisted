#!/usr/bin/env python3
"""Generate kicad/pc817_bench.kicad_pcb: an Arduino UNO shield, two layers, through-hole.

Must run with KiCad's own Python (it needs the pcbnew module), after generate.py and after
the netlist has been exported -- check.sh does all of it in order:
    python3 generate.py
    kicad-cli sch export netlist -o kicad/pc817_bench.net kicad/pc817_bench.kicad_sch
    python3 generate_pcb.py              (KiCad's python)

Coordinates below are in millimetres, x to the right, y down, seen from the component side
of the shield with the Arduino's USB connector on the left. The digital header is then the
top row (y = 0) and the power/analog header the bottom row (y = 48.26); x = 0 is the first
pin of the power header.

The library footprint Module:Arduino_UNO_R3 is drawn for an Arduino lying on the SAME side
as the parts. A shield sits ABOVE the Arduino, so the footprint is flipped to the back side;
unflipped, the shield would come out mirrored and would only fit upside down.
"""
import os
import re
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
OUT = HERE / "kicad" / "pc817_bench.kicad_pcb"
NETLIST = HERE / "kicad" / "pc817_bench.net"
ORIGIN = (120.0, 80.0)          # where Arduino pin 1 sits on the sheet

F, B = pcbnew.F_Cu, pcbnew.B_Cu
TRACK_W = 0.5


def find_footprint_dir():
    for var in ("KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD8_FOOTPRINT_DIR"):
        if os.environ.get(var):
            return os.environ[var]
    for d in ("/app/extensions/Library/Footprints/footprints", "/usr/share/kicad/footprints"):
        if os.path.isdir(d):
            return d
    sys.exit("KiCad footprint libraries not found; set KICAD10_FOOTPRINT_DIR")


FP_DIR = find_footprint_dir()


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(ORIGIN[0] + x), pcbnew.FromMM(ORIGIN[1] + y))


# --------------------------------------------------------------------------- netlist
def read_netlist(path):
    """Returns ({ref: (footprint, value, symbol uuid)}, {(ref, pad): net name})."""
    text = path.read_text()
    comps, nets = {}, {}
    for blk in re.split(r"\(comp\s", text)[1:]:
        ref = re.search(r'\(ref "([^"]+)"', blk).group(1)
        comps[ref] = (re.search(r'\(footprint "([^"]+)"', blk).group(1),
                      re.search(r'\(value "([^"]*)"', blk).group(1),
                      re.search(r'\(tstamps "([^"]+)"', blk).group(1))
    for blk in re.split(r"\(net\s+\(code", text[text.index("(nets"):])[1:]:
        name = re.search(r'\(name "([^"]*)"', blk).group(1)
        for ref, pad in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"', blk):
            nets[(ref, pad)] = name
    return comps, nets


COMPS, PAD_NET = read_netlist(NETLIST)
board = pcbnew.BOARD()
NETS = {}


def net(name):
    if name not in NETS:
        NETS[name] = pcbnew.NETINFO_ITEM(board, name)
        board.Add(NETS[name])
    return NETS[name]


# --------------------------------------------------------------------------- placement
# Four identical channels stacked top to bottom. ROWS gives, per row: the schematic channel
# number and the y of its resistor line. The order is set by the header: each row's output
# has its own way up to the digital header without crossing the others (see route_logic).
ROW_PITCH = 10.0
ROWS = [(3, 4.5), (2, 14.5), (1, 24.5), (4, 34.5)]      # lidar 1, e-stop 2, e-stop 1, lidar 2
ARDUINO_PAD = {1: "17", 2: "18", 3: "19", 4: "20"}      # channel -> pad of D2, D3, D4, D5
TERMINAL = {3: "3", 2: "5", 1: "7", 4: "8"}             # channel -> J1 terminal of its input
RAIL_DY = 8.3                                           # 24 V return rail under each channel
BUS_X = 15.3                                            # 24 V return bus, between LED and optocoupler
LOGIC_GND_X = 32.9
CAP_X = 27.5                                            # capacitors, right of the optocouplers
OUT_LANE = {1: 29.5, 2: 31.2}                           # middle rows: way up, clear of the capacitors
J1_X, J1_Y, FUSE_Y = -22.0, 10.3, 3.0


def refs(ch):
    return {"r": "R%d" % ch, "led": "D%d" % ch,
            "dio": "D%d" % (ch + 4), "u": "U%d" % ch, "rp": "R%d" % (ch + 4), "c": "C%d" % ch}


# ref: (x, y, rotation) of the footprint origin (= pad 1 for these footprints)
PLACE = {"A1": (0.0, 48.26, 0), "J1": (J1_X, J1_Y, 270), "F1": (-20.5, FUSE_Y, 180)}
for ch, y0 in ROWS:
    r = refs(ch)
    PLACE.update({
        r["r"]:   (-2.24, y0 - 0.3, 0),      # series resistor, 1/2 W: input -> N (pad 2 above the LED anode;
                                             # 0.3 mm up so its wider body clears the LED)
        r["led"]: (13.0, y0 + 4.0, 180),     # indicator LED, anode on the left, under the end of the resistor
        r["dio"]: (7.4, y0 + 4.0, 180),      # 1N4148, cathode on the right, next to the LED anode
        r["u"]:   (17.5, y0 + 4.0, 0),       # PC817: pins 1-2 on the 24 V side
        r["rp"]:  (35.28, y0, 180),          # pull-up, pad 2 right above the collector
        r["c"]:   (CAP_X, y0 + 4.04, 270),   # optional filter capacitor, across pins 4 and 3
    })

FPS = {}
for ref, (x, y, rot) in PLACE.items():
    lib, name = COMPS[ref][0].split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FP_DIR, lib + ".pretty"), name)
    if fp is None:
        sys.exit("footprint not found: %s" % COMPS[ref][0])
    fp.SetReference(ref)
    fp.SetValue(COMPS[ref][1])
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPath(pcbnew.KIID_PATH("/" + COMPS[ref][2]))
    fp.SetPosition(mm(x, y))
    fp.SetOrientationDegrees(rot)
    for pad_ in fp.Pads():
        name_ = PAD_NET.get((ref, pad_.GetNumber()))
        if name_:
            pad_.SetNet(net(name_))
    board.Add(fp)
    FPS[ref] = fp
missing = set(COMPS) - set(PLACE)
if missing:
    sys.exit("no placement for: %s" % sorted(missing))

# The library footprint describes an Arduino mounted ON a board: its courtyard and outline
# cover the whole area. On a shield the parts sit inside that area, so both are removed, and
# the footprint is flipped to the back because the Arduino is under the shield.
# (Done after every footprint is loaded: touching a footprint earlier breaks
# pcbnew.FootprintLoad in KiCad 10.)
FPS["A1"].Flip(mm(*PLACE["A1"][:2]), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
for g in list(FPS["A1"].GraphicalItems()):
    if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.F_SilkS, pcbnew.B_CrtYd, pcbnew.B_SilkS):
        FPS["A1"].Remove(g)


def ref_text(ref, x, y, size=0.8):
    t = FPS[ref].Reference()
    t.SetPosition(mm(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(0.12))
    t.SetTextAngleDegrees(0)


# reference texts: on the part's own outline (hidden once assembled) where rows are too close
for ch, y0 in ROWS:
    r = refs(ch)
    ref_text(r["r"], 4.11, y0 - 0.3)
    ref_text(r["rp"], 30.2, y0)
    ref_text(r["c"], 30.2, y0 + 5.3)
    ref_text(r["dio"], 3.6, y0 + 6.0)
    ref_text(r["led"], 13.6, y0 + 1.4)
    ref_text(r["u"], 21.3, y0 + 5.27)
ref_text("F1", -15.0, 1.0)
ref_text("J1", -22.0, 43.5)


def pad(ref, num):
    """Pad centre in local millimetres, and its net name."""
    p = next(p for p in FPS[ref].Pads() if p.GetNumber() == num)
    pos = p.GetPosition()
    return (round(pcbnew.ToMM(pos.x) - ORIGIN[0], 3), round(pcbnew.ToMM(pos.y) - ORIGIN[1], 3)), p.GetNetname()


# --------------------------------------------------------------------------- routing
def route(layer, netname, *pts, width=TRACK_W):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(mm(*a)); t.SetEnd(mm(*b))
        t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(layer); t.SetNet(net(netname))
        board.Add(t)


LANES = [-18.8, -17.1, -15.4, -14.0]       # where each input track turns towards its row


def route_channel(row, ch, y0):
    r = refs(ch)
    ra1, n_in = pad(r["r"], "1")
    rb2, n_n = pad(r["r"], "2")
    led_a, _ = pad(r["led"], "2")
    led_k, n_k = pad(r["led"], "1")
    dio_k, _ = pad(r["dio"], "1")
    dio_a, n_g24 = pad(r["dio"], "2")
    u1, _ = pad(r["u"], "1")
    u2, _ = pad(r["u"], "2")
    u3, n_gnd = pad(r["u"], "3")
    u4, n_out = pad(r["u"], "4")
    rp1, n_ioref = pad(r["rp"], "1")
    rp2, _ = pad(r["rp"], "2")
    jin, _ = pad("J1", TERMINAL[ch])

    # 24 V side, component layer
    route(F, n_in, jin, (LANES[row], jin[1]), (LANES[row], ra1[1]), ra1)
    route(F, n_n, rb2, led_a, dio_k)
    route(F, n_k, led_k, u1)
    # 24 V return, solder layer: a rail under the channel
    rail = y0 + RAIL_DY
    route(B, n_g24, u2, (u2[0], rail), (dio_a[0], rail), dio_a)

    # logic side: collector to its pull-up, then to its header pin
    route(F, n_out, rp2, u4)
    header, _ = pad("A1", ARDUINO_PAD[ch])
    if row == 0:                    # top row: straight up from the pull-up pad
        route(F, n_out, rp2, header)
    elif row == 3:                  # bottom row: up through the gap under the optocouplers
        route(B, n_out, u4, (header[0], u4[1]), header)
    else:                           # middle rows: one lane each, right of the capacitors
        lane = OUT_LANE[row]
        route(B, n_out, u4, (lane, u4[1]), (lane, 2.4), (header[0], 2.4 - (lane - header[0])), header)
    route(F, n_gnd, u3, (LOGIC_GND_X, u3[1]))
    c1, _ = pad(r["c"], "1")
    route(F, n_out, u4, c1)         # capacitor: output side; its GND pad sits on the GND link above
    return rail, n_g24, n_gnd, n_ioref, u3, rp1


res = [route_channel(i, ch, y0) for i, (ch, y0) in enumerate(ROWS)]
rails = [x[0] for x in res]
n_g24, n_gnd, n_ioref = res[0][1], res[0][2], res[0][3]

# 24 V return: bus joining the four rails, and the two 0V terminals
route(B, n_g24, (BUS_X, rails[0]), (BUS_X, rails[-1]))
dio_x = pad(refs(ROWS[0][0])["dio"], "2")[0][0]
t0v_top, _ = pad("J1", "2")
t0v_bot, _ = pad("J1", "9")
route(B, n_g24, t0v_top, (t0v_top[0] + 1.0, rails[0]), (dio_x, rails[0]))
route(B, n_g24, t0v_bot, (t0v_bot[0] + 4.5, rails[-1]), (dio_x, rails[-1]))

# fused 24 V: supply terminal -> fuse -> the two ES+ terminals. 1 mm wide: this is the path
# a short on a button cable would load until the fuse opens. The bus runs left of the terminals.
t24, n_24in = pad("J1", "1")
f1a, _ = pad("F1", "1")
f1b, n_24 = pad("F1", "2")
route(F, n_24in, t24, (f1a[0], t24[1] - 1.5), f1a, width=1.0)
for term in ("4", "6"):
    tp, _ = pad("J1", term)
    route(B, n_24, f1b, (f1b[0], tp[1]), tp, width=1.0)

# IOREF: the four pull-ups in a column, then along the bottom to the header pin, solder side
BOTTOM_Y = 46.2
ioref_pin, _ = pad("A1", "2")
route(B, n_ioref, res[0][5], res[-1][5], (res[-1][5][0], BOTTOM_Y), (ioref_pin[0], BOTTOM_Y), ioref_pin)

# logic GND: a column joining the four emitters, then along the bottom to the two GND pins
g6, _ = pad("A1", "6")
g7, _ = pad("A1", "7")
route(F, n_gnd, (LOGIC_GND_X, res[0][4][1]), (LOGIC_GND_X, BOTTOM_Y), (g7[0], BOTTOM_Y), g7, g6)


# --------------------------------------------------------------------------- outline, silk
def line(layer, a, b, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(mm(*a)); s.SetEnd(mm(*b)); s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(width))
    board.Add(s)


def silk(text, x, y, size=1.0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text); t.SetPosition(mm(x, y)); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(t)


# board edge: the UNO rectangle (the Arduino's own outline, without its right-hand bulge)
X0, Y0, X1, Y1 = -27.94, -2.54, 38.1, 50.8
for a, b in (((X0, Y0), (X1, Y0)), ((X1, Y0), (X1, Y1)), ((X1, Y1), (X0, Y1)), ((X0, Y1), (X0, Y0))):
    line(pcbnew.Edge_Cuts, a, b)

# isolation barrier, drawn between the two pin rows of the optocouplers, outside their bodies
BARRIER_X = 20.4
for y in range(3, 45):
    if not any(y0 + 2.4 <= y <= y0 + 8.2 for _, y0 in ROWS):
        line(pcbnew.F_SilkS, (BARRIER_X, y), (BARRIER_X, y + 0.6), 0.15)

# terminal names, right of the block
for i, name in enumerate(("24V", "0V", "L1", "ES2+", "ES2", "ES1+", "ES1", "L2", "0V")):
    silk(name, -15.9 if i not in (2, 4) else -15.2, J1_Y + 3.5 * i - (1.2 if i in (2, 4, 6, 7) else 0), 0.8)
silk("SAFETY INPUTS", -14.0, 44.2, 1.0)
silk("UNO R4 WiFi / UNO Q", -14.0, 46.3, 0.8)

OUT.parent.mkdir(exist_ok=True)
pcbnew.SaveBoard(str(OUT), board)
print("written: %s (%d footprints, %d tracks)" % (OUT.name, len(FPS), len(board.GetTracks())))
