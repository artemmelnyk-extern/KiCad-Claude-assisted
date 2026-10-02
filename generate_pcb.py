#!/usr/bin/env python3
"""PROTO-SHIELD VARIANT. Generate kicad/pc817_bench.kicad_pcb as a model of the hand-built board.

Nothing here is meant to be manufactured: the board is a proto shield whose holes already
exist. The KiCad file is a model of the build plan in generate_protoboard.py, so that KiCad
can check it:

  * every part sits on the 2.54 mm grid, with the footprint of how it is mounted
    (resistors and diodes upright);
  * solder bridges and bare-wire runs are tracks on the solder side (B.Cu);
  * insulated wires are NOT copper: they are drawn on the Cmts.User layer and stay as
    ratsnest lines. KiCad therefore reports exactly one "unconnected" item per wire.

Must run with KiCad's own Python (module pcbnew), after generate.py and the netlist export.

Coordinates: x right, y down, component side, USB on the left. The digital header is the
row y = 0, the power header the row y = 48.26, and x = 0 is the first pin of the power
header. Where the grid sits on a real proto shield is an ASSUMPTION (GRID_X0, GRID_Y0):
measure the board.
"""
import os
import re
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_protoboard as plan      # the build plan: holes, bridges, bare wires, wires

OUT = HERE / "kicad" / "pc817_bench.kicad_pcb"
ORIGIN = (120.0, 80.0)
P = 2.54
GRID_X0, GRID_Y0 = -22.86, 5.08         # position of hole (row 0, col 0)
F, B = pcbnew.F_Cu, pcbnew.B_Cu


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


def hole_xy(h):
    return GRID_X0 + h[1] * P, GRID_Y0 + h[0] * P


# --------------------------------------------------------------------------- netlist
def read_netlist(path):
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


COMPS, PAD_NET = read_netlist(plan.NETLIST)
board = pcbnew.BOARD()
NETS = {}


def net(name):
    if name not in NETS:
        NETS[name] = pcbnew.NETINFO_ITEM(board, name)
        board.Add(NETS[name])
    return NETS[name]


# --------------------------------------------------------------------------- placement
# where each pad must land: {ref: {pad number: hole}}, straight from the plan
TARGET = {}
for h, (ref, num) in plan.legs.items():
    TARGET.setdefault(ref, {})[num] = h
TARGET["J1"] = {str(i + 1): (plan.TERM_ROW[i], 0) for i in range(len(plan.TERMINALS))}

FPS = {}


def load(ref):
    lib, name = COMPS[ref][0].split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FP_DIR, lib + ".pretty"), name)
    if fp is None:
        sys.exit("footprint not found: %s" % COMPS[ref][0])
    fp.SetReference(ref)
    fp.SetValue(COMPS[ref][1])
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPath(pcbnew.KIID_PATH("/" + COMPS[ref][2]))
    for p in fp.Pads():
        n = PAD_NET.get((ref, p.GetNumber()))
        if n:
            p.SetNet(net(n))
    board.Add(fp)
    FPS[ref] = fp
    return fp


for ref in COMPS:           # load everything first (KiCad 10: modifying a footprint breaks later loads)
    load(ref)


def pad_mm(p):
    pos = p.GetPosition()
    return pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1]


def place_on_grid(ref):
    """Try the four rotations until every pad lands in its hole of the plan."""
    fp, want = FPS[ref], TARGET[ref]
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        p1 = next(p for p in fp.Pads() if p.GetNumber() == "1")
        x1, y1 = pad_mm(p1)
        tx, ty = hole_xy(want["1"])
        cur = fp.GetPosition()
        fp.SetPosition(pcbnew.VECTOR2I(cur.x + pcbnew.FromMM(tx - x1), cur.y + pcbnew.FromMM(ty - y1)))
        if all(max(abs(a - b) for a, b in zip(pad_mm(p), hole_xy(want[p.GetNumber()]))) < 0.01 for p in fp.Pads()):
            return rot
    sys.exit("%s (%s) does not fit its holes %s in any rotation" % (ref, COMPS[ref][0], want))


missing = set(COMPS) - set(TARGET) - {"A1"}
if missing:
    sys.exit("parts not in the build plan: %s" % sorted(missing))
for ref in TARGET:
    place_on_grid(ref)

# Arduino header: under the shield, so flipped to the back; its courtyard and outline cover
# the whole board and are removed (see the main branch for the reasoning).
FPS["A1"].SetPosition(mm(0.0, 48.26))
FPS["A1"].Flip(mm(0.0, 48.26), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
for g in list(FPS["A1"].GraphicalItems()):
    if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.F_SilkS, pcbnew.B_CrtYd, pcbnew.B_SilkS):
        FPS["A1"].Remove(g)


# --------------------------------------------------------------------------- solder side
def track(a, b, width):
    name = plan.HOLE_NET.get(a) or plan.HOLE_NET.get(b)
    if name is None:
        sys.exit("no net for the run %s -> %s" % (a, b))
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(mm(*hole_xy(a))); t.SetEnd(mm(*hole_xy(b)))
    t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(B); t.SetNet(net(name))
    board.Add(t)


for a, b in plan.bridges:
    track(a, b, 1.2)                    # solder bridge
for run in plan.buses:
    for a, b in zip(run, run[1:]):
        track(a, b, 0.9)                # bare wire


# --------------------------------------------------------------------------- drawings
def shape(layer, kind, a, b, width):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(kind)
    if kind == pcbnew.SHAPE_T_CIRCLE:
        s.SetCenter(mm(*a)); s.SetEnd(mm(a[0] + b, a[1]))
    else:
        s.SetStart(mm(*a)); s.SetEnd(mm(*b))
    s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(width))
    board.Add(s)


def text(layer, s, x, y, size=1.0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s); t.SetPosition(mm(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(t)


X0, Y0, X1, Y1 = -27.94, -2.54, 38.1, 50.8                 # UNO shield rectangle
for a, b in (((X0, Y0), (X1, Y0)), ((X1, Y0), (X1, Y1)), ((X1, Y1), (X0, Y1)), ((X0, Y1), (X0, Y0))):
    shape(pcbnew.Edge_Cuts, pcbnew.SHAPE_T_SEGMENT, a, b, 0.1)

# the grid of the plan, for reference (Dwgs.User): one circle per hole, numbered rows and columns
for r in range(plan.ROWS):
    text(pcbnew.Dwgs_User, str(r), GRID_X0 + plan.COLS * P + 1.0, GRID_Y0 + r * P, 0.8)
    for c in range(plan.COLS):
        shape(pcbnew.Dwgs_User, pcbnew.SHAPE_T_CIRCLE, hole_xy((r, c)), 0.5, 0.05)
for c in range(plan.COLS):
    text(pcbnew.Dwgs_User, str(c), GRID_X0 + c * P, GRID_Y0 + plan.ROWS * P, 0.8)

# insulated wires (Cmts.User): from a hole to a hole, or to a header pin
HEADER_PAD = {"D2": "17", "D3": "18", "D4": "19", "D5": "20", "IOREF": "2", "GND": "7"}
for a, b, _, why in plan.wires:
    if isinstance(b, str):
        end = pad_mm(next(p for p in FPS["A1"].Pads() if p.GetNumber() == HEADER_PAD[b]))
    else:
        end = hole_xy(b)
    shape(pcbnew.Cmts_User, pcbnew.SHAPE_T_SEGMENT, hole_xy(a), end, 0.3)
text(pcbnew.Cmts_User, "Cmts.User lines = insulated wires", 22.0, 44.0, 0.8)

for ref, fp in FPS.items():            # keep the reference texts small: the grid is dense
    t = fp.Reference()
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
    t.SetTextThickness(pcbnew.FromMM(0.12))

OUT.parent.mkdir(exist_ok=True)
pcbnew.SaveBoard(str(OUT), board)
print("written: %s (%d footprints on the grid, %d solder-side runs, %d wires as ratsnest)"
      % (OUT.name, len(FPS), len(board.GetTracks()), len(plan.wires)))
