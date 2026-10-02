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
# ref: (x, y, rotation in degrees) of the footprint origin (= pad 1 for these footprints)
def channel_placement(k, y0):
    """Channel k (1 or 2) laid out left to right starting on the line y0."""
    r = 2 * k - 1
    return {
        "R%d" % r:       (-12.0, y0, 0),          # series resistor 1: input -> M
        "R%d" % (r + 1): (1.2, y0, 0),            # series resistor 2: M -> N
        "D%d" % k:       (13.9, y0 + 5.0, 180),   # indicator LED, anode on the left
        "D%d" % (k + 2): (11.36, y0 + 9.0, 180),  # 1N4148, cathode on the right
        "U%d" % k:       (18.0, y0 + 5.0, 0),     # PC817: pins 1-2 on the 24 V side
        "R%d" % (k + 4): (35.78, y0, 180),        # pull-up, pad 2 above the collector
    }


HEADER_PITCH_Y = 48.26
# J1: 6 screw terminals down the left edge. F1: fuse above it, on the incoming 24 V.
PLACE = {"A1": (0.0, HEADER_PITCH_Y, 0), "J1": (-21.0, 11.0, 270), "F1": (-21.0, 3.0, 0)}
PLACE.update(channel_placement(1, 8.0))
PLACE.update(channel_placement(2, 26.0))

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
    for pad in fp.Pads():
        name_ = PAD_NET.get((ref, pad.GetNumber()))
        if name_:
            pad.SetNet(net(name_))
    board.Add(fp)
    FPS[ref] = fp
# The library footprint describes an Arduino mounted ON a board: its courtyard and outline
# cover the whole area. On a shield the parts sit inside that area, so both are removed.
# (Done after every footprint is loaded: touching GraphicalItems() earlier breaks
# pcbnew.FootprintLoad in KiCad 10.)
FPS["A1"].Flip(mm(*PLACE["A1"][:2]), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)    # the Arduino is under the shield
for g in list(FPS["A1"].GraphicalItems()):
    if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.F_SilkS, pcbnew.B_CrtYd, pcbnew.B_SilkS):
        FPS["A1"].Remove(g)
# LED reference texts: moved up, clear of the diode pad below
for k, y0 in ((1, 8.0), (2, 26.0)):
    FPS["D%d" % k].Reference().SetPosition(mm(14.6, y0 + 2.2))
FPS["J1"].Reference().SetPosition(mm(-21.0, 41.0))      # below the terminal block
FPS["F1"].Reference().SetPosition(mm(-11.5, 3.0))       # beside the fuse, inside the board
missing = set(COMPS) - set(PLACE)
if missing:
    sys.exit("no placement for: %s" % sorted(missing))


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


def via(netname, p):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(mm(*p)); v.SetWidth(F, pcbnew.FromMM(1.2)); v.SetDrill(pcbnew.FromMM(0.6))
    v.SetLayerPair(F, B); v.SetNet(net(netname))
    board.Add(v)


def route_channel(k, y0):
    r = 2 * k - 1
    ra1, n_in = pad("R%d" % r, "1")
    ra2, n_m = pad("R%d" % r, "2")
    rb1, _ = pad("R%d" % (r + 1), "1")
    rb2, n_n = pad("R%d" % (r + 1), "2")
    led_a, _ = pad("D%d" % k, "2")
    led_k, n_k = pad("D%d" % k, "1")
    dio_k, _ = pad("D%d" % (k + 2), "1")
    dio_a, n_g24 = pad("D%d" % (k + 2), "2")
    u1, _ = pad("U%d" % k, "1")
    u2, _ = pad("U%d" % k, "2")
    u3, n_gnd = pad("U%d" % k, "3")
    u4, n_out = pad("U%d" % k, "4")
    rp1, n_ioref = pad("R%d" % (k + 4), "1")
    rp2, _ = pad("R%d" % (k + 4), "2")
    jin, _ = pad("J1", str(2 * k + 1))                    # ES1 = terminal 3, ES2 = terminal 5

    # 24 V side, component layer
    route(F, n_in, jin, (ra1[0], jin[1]), ra1)
    route(F, n_m, ra2, rb1)
    route(F, n_n, rb2, led_a, dio_k)
    route(F, n_k, led_k, u1)
    # 24 V return, solder layer: a rail under the channel, joined by a bus on the left
    rail = y0 + 11.5
    route(B, n_g24, u2, (u2[0], rail), (dio_a[0], rail), dio_a)
    # logic side
    route(F, n_out, rp2, u4)
    header, _ = pad("A1", "17" if k == 1 else "18")       # D2, D3 on the top row
    if k == 1:      # from the pull-up pad, component side, above channel 1
        route(F, n_out, rp2, (rp2[0], 4.5), (header[0], 4.5), header)
    else:           # solder side, straight up past channel 1
        route(B, n_out, u4, (header[0], u4[1]), header)
    return rail, u3, n_gnd, rp1, n_ioref, n_g24


GND24_BUS_X = 16.0          # between the LED and the optocoupler, solder side
rail1, gnd1, n_gnd, io1, n_ioref, n_g24 = route_channel(1, 8.0)
rail2, gnd2, _, io2, _, _ = route_channel(2, 26.0)

# 24 V return bus and its terminal
dio4_a, _ = pad("D4", "2")
j0v, _ = pad("J1", "6")
route(B, n_g24, (GND24_BUS_X, rail1), (GND24_BUS_X, rail2))
route(B, n_g24, (dio4_a[0], rail2), (j0v[0] + 1.5, rail2), j0v)

# fused 24 V: supply terminal -> fuse -> the two ES+ terminals. 1 mm wide: this is the path
# a short on a button cable would load until the fuse opens.
jin24, n_24in = pad("J1", "1")
f1a, _ = pad("F1", "1")
f1b, n_24 = pad("F1", "2")
es1p, _ = pad("J1", "2")
es2p, _ = pad("J1", "4")
route(F, n_24in, jin24, f1a, width=1.0)
route(B, n_24, f1b, (f1b[0], es1p[1]), es1p, width=1.0)
route(B, n_24, (f1b[0], es1p[1]), (f1b[0], es2p[1]), es2p, width=1.0)

# IOREF: both pull-ups, then along the bottom to the header pin, solder side
ioref_pin, _ = pad("A1", "2")
route(B, n_ioref, io1, io2, (io2[0], 44.5), (ioref_pin[0], 44.5), ioref_pin)

# logic GND: both emitters, then down to the two GND pins of the power header
g6, _ = pad("A1", "6")
g7, _ = pad("A1", "7")
route(F, n_gnd, gnd1, (33.0, gnd1[1]), (33.0, gnd2[1]), gnd2)
route(F, n_gnd, (33.0, gnd2[1]), (33.0, 41.5), (g7[0], 41.5), g7, g6)


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

# isolation barrier, drawn between the two pin rows of the optocouplers
BARRIER_X = 21.8
for y in range(5, 39, 2):
    if not any(y0 + 3 <= y <= y0 + 9.5 for y0 in (8.0, 26.0)):     # skip the optocoupler bodies
        line(pcbnew.F_SilkS, (BARRIER_X, y), (BARRIER_X, y + 1), 0.15)
silk("24V SIDE", 3.0, 41.0)
silk("LOGIC", 29.5, 22.5)
silk("E-STOP INPUTS", 0.0, 3.0, 1.2)
silk("UNO R4 WiFi / UNO Q", -16.0, 46.0)
# terminal names, printed inside the board next to each screw (right of the block)
for i, name in enumerate(("24V", "ES1+", "ES1", "ES2+", "ES2", "0V")):
    silk(name, -13.3, 9.6 + 5.0 * i, 0.8)

OUT.parent.mkdir(exist_ok=True)
pcbnew.SaveBoard(str(OUT), board)
print("written: %s (%d footprints, %d tracks)" % (OUT.name, len(FPS), len(board.GetTracks())))
