#!/usr/bin/env python3
"""Build plan for the green ElectroCookie "Uno ProtoShield Universal" (all pads isolated).

Writes protoboard/layout.png, protoboard/layout.pdf (1:1 when printed at 100 %) and
protoboard/BUILD.md (hole-by-hole tables). Before writing, it checks that the holes joined
by the plan form exactly the nets of the KiCad schematic (kicad/pc817_bench.net), and that
every hole it uses exists on the board.

Needs matplotlib. Run: python3 generate_protoboard.py   (after generate.py + netlist export)

HOLES ARE NAMED (row, column), seen from the COMPONENT side with the Arduino's USB end up:
  * columns 1..20 are the numbers printed along the top edge of the board;
  * row 1 is the row next to those numbers, rows count downwards to 25.
The power/analog header is then on the left edge and the digital header on the right edge.
The hole map below was read from a photo, then confirmed on the real board (2026-10-05).
"""
import re
import sys
from pathlib import Path

try:                                    # only the drawing needs matplotlib; the plan itself
    import matplotlib                   # is also imported by generate_pcb.py under KiCad's Python
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
except ImportError:
    plt = None

HERE = Path(__file__).resolve().parent
OUT = HERE / "protoboard"
NETLIST = HERE / "kicad" / "pc817_bench.net"

# ----------------------------------------------------------------------------- the board
ROWS, COLS = 25, 20
FREE = set()                                    # isolated pads
for r in range(1, 5):
    FREE |= {(r, c) for c in range(1, 21)}
for r in range(5, 7):
    FREE |= {(r, c) for c in range(1, 19)}      # mounting hole at the right
for r in range(7, 10):
    FREE |= {(r, c) for c in range(1, 18)}      # header labels at the right
FREE |= {(10, c) for c in range(3, 18)}
for r in range(11, 26):
    FREE |= {(r, c) for c in range(4, 18)}      # between the two headers
# pads printed joined to a header pin (the inner column of each double row): wires land here
HEADER_HOLE = {"IOREF": (12, 2), "GND": (16, 2), "D5": (20, 19), "D4": (21, 19), "D3": (22, 19), "D2": (23, 19)}
HEADER_LABELS = {(11, 2): "", (12, 2): "IOREF", (13, 2): "RES", (14, 2): "3V3", (15, 2): "5V", (16, 2): "GND",
                 (17, 2): "GND", (18, 2): "Vin", (18, 19): "D7", (19, 19): "D6", (20, 19): "D5", (21, 19): "D4",
                 (22, 19): "D3", (23, 19): "D2", (24, 19): "TX1", (25, 19): "RX0"}
JACK = (1, 2, 5, 5)                             # rows 1-5, columns 2-5: above the Arduino's power jack

# ----------------------------------------------------------------------------- the plan
# Screw terminals, 5.08 mm pitch (every second hole), along row 1, wires entering from the top.
TERMINALS = ["24V", "ES+", "ES1", "ES2", "L1", "L2", "0V", "0V"]
TERM_HOLES = [(1, 6 + 2 * i) for i in range(len(TERMINALS))]
LAND_ROW = 4                                    # first row clear of the terminal block's body

# channel: (schematic number, first of its two columns, input name, Arduino pin, resistor value)
CHANNELS = [(1, 6, "ES1", "D2", "3.3k 1/2W"), (2, 9, "ES2", "D3", "3.3k 1/2W"),
            (3, 12, "L1", "D4", "4.7k 1/2W"), (4, 15, "L2", "D5", "4.7k 1/2W")]
# Each channel runs DOWN the board in two neighbouring columns k, k+1 (k+2 is its spare column):
R_BUS0V, R_R1, R_R2, R_DA, R_LED_A, R_LED_K, R_U12, R_U43, R_OUT, R_C, R_IOREF = 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20
ISOLATION_ROWS = (15, 16)                       # under the optocouplers: nothing here

legs = {}        # hole -> (ref, pin)        part legs
ends = {}        # hole -> name              terminals and wire landings
parts = []       # (ref, kind, value, [hole, ...])
bridges = []     # (hole, hole): solder bridge between neighbouring pads, solder side
buses = []       # [hole, hole, ...]: bare wire soldered along a line of pads, solder side
wires = []       # (hole, hole or header name, colour, note): insulated wire, component side


def part(ref, kind, value, pins):
    parts.append((ref, kind, value, [h for _, h in pins]))
    for num, h in pins:
        assert h not in legs, "hole used twice: %s" % (h,)
        legs[h] = (ref, num)


def bridge(a, b):
    assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, "not neighbours: %s %s" % (a, b)
    bridges.append((a, b))


for ch, k, name, pin, rval in CHANNELS:
    # k is the channel's main column; k-1 its second column, k-2 its spare column (0V strip).
    # 24 V side, top to bottom
    part("R%d" % ch, "R", rval, [("1", (R_R1, k)), ("2", (R_R2, k))])              # upright, body on pin 1
    ends[(R_R1, k - 1)] = "%s in" % name
    bridge((R_R1, k - 1), (R_R1, k))                                                # input wire -> resistor
    buses.append([(r, k) for r in range(R_R2, R_LED_A + 1)])                        # resistor -> LED anode
    part("D%d" % ch, "LED", "LED", [("2", (R_LED_A, k)), ("1", (R_LED_K, k))])      # 2 = anode
    part("D%d" % (ch + 4), "D", "1N4148", [("1", (R_LED_A, k - 1)), ("2", (R_DA, k - 1))])   # 1 = cathode
    bridge((R_LED_A, k), (R_LED_A, k - 1))                                          # LED anode -> diode cathode
    bridge((R_DA, k - 1), (R_DA, k - 2))                                            # diode anode -> 0V strip
    # PC817 seen from above: pin 1 top right, 2 top left, 3 bottom left, 4 bottom right
    part("U%d" % ch, "U", "PC817", [("1", (R_U12, k)), ("2", (R_U12, k - 1)),
                                    ("3", (R_U43, k - 1)), ("4", (R_U43, k))])
    bridge((R_LED_K, k), (R_U12, k))                                                # LED cathode -> pin 1
    # 0V strip in the channel's spare column, from pin 2 up to the 0V bus
    buses.append([(R_U12, k - 1), (R_U12, k - 2)] + [(r, k - 2) for r in range(R_U12 - 1, R_BUS0V - 1, -1)])
    # logic side
    part("R%d" % (ch + 4), "R", "10k", [("2", (R_OUT, k)), ("1", (R_C, k))])        # pull-up, upright
    bridge((R_U43, k), (R_OUT, k))                                                  # collector -> pull-up
    bridge((R_C, k), (R_IOREF, k))                                                  # pull-up -> IOREF bus
    ends[(R_OUT, k + 1)] = "%s out" % pin
    bridge((R_OUT, k + 1), (R_OUT, k))                                              # ... -> output wire landing
    ends[(R_OUT, k - 1)] = "GND"
    bridge((R_U43, k - 1), (R_OUT, k - 1))                                          # emitter -> GND wire landing
    # optional filter capacitor, in the two columns right of the channel
    part("C%d" % ch, "C", "100n opt.", [("1", (R_C, k + 1)), ("2", (R_C, k + 2))])
    bridge((R_OUT, k + 1), (R_C, k + 1))                                            # output landing -> capacitor
    bridge((R_OUT, k + 2), (R_C, k + 2))                                            # GND pad -> capacitor
    wires.append(((R_OUT, k + 1), pin, "tab:blue", "output"))

first_k, last_k = CHANNELS[0][1], CHANNELS[-1][1]
# 0V bus along row 8, joined to the two 0V terminals through column 18 / 17
buses.append([(R_BUS0V, c) for c in range(first_k - 2, 18)])
t0v = [h for h, n in zip(TERM_HOLES, TERMINALS) if n == "0V"]
buses.append([(r, t0v[0][1]) for r in range(1, 7)] + [(6, 17), (7, 17), (R_BUS0V, 17)])
buses.append([(r, t0v[1][1]) for r in range(1, 5)] + [(4, 19), (4, 18)])
# fused 24 V: 24V terminal -> down column 6 -> fuse -> up column 8 -> ES+ terminal
part("F1", "F", "T2A", [("1", (6, 6)), ("2", (6, 8))])
buses.append([(r, 6) for r in range(1, 7)])
buses.append([(r, 8) for r in range(6, 0, -1)])
# inputs: terminal -> bare wire down to the landing row -> insulated wire to the channel
for ch, k, name, pin, rval in CHANNELS:
    th = TERM_HOLES[TERMINALS.index(name)]
    buses.append([(r, th[1]) for r in range(1, LAND_ROW + 1)])
    ends[(LAND_ROW, th[1])] = name
    wires.append(((LAND_ROW, th[1]), (R_R1, k - 1), "tab:orange", "input"))
for h, name in zip(TERM_HOLES, TERMINALS):
    ends[h] = "T:" + name
# IOREF bus along row 20
buses.append([(R_IOREF, c) for c in range(first_k, last_k + 1)])
ends[(R_IOREF, last_k + 1)] = "IOREF"
bridge((R_IOREF, last_k), (R_IOREF, last_k + 1))
wires.append(((R_IOREF, last_k + 1), "IOREF", "tab:purple", "logic supply reference"))
# logic GND: daisy chain along row 18, then to the header
gnd = [(R_OUT, k - 1) for _, k, _, _, _ in CHANNELS] + [(R_OUT, last_k + 2)]
ends[gnd[-1]] = "GND"
for a, b in zip(gnd, gnd[1:]):
    wires.append((a, b, "black", "logic GND"))
wires.append((gnd[0], "GND", "black", "logic GND"))


# ----------------------------------------------------------------------------- checks
HOLE_NET = {}       # hole -> schematic net name, for every pad the plan uses


def check_against_schematic():
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    used = set(legs) | set(ends)
    for a, b in bridges:
        union(a, b); used |= {a, b}
    for b in buses:
        for x, y in zip(b, b[1:]):
            assert abs(x[0] - y[0]) + abs(x[1] - y[1]) == 1, "bus not contiguous: %s %s" % (x, y)
            union(x, y)
        used |= set(b)
    for a, b, _, _ in wires:
        union(a, ("header", b) if isinstance(b, str) else b)
    errors = ["hole %s is used but does not exist on the board" % (h,) for h in sorted(used - FREE)]
    errors += ["hole %s is in the isolation rows" % (h,) for h in sorted(used) if h[0] in ISOLATION_ROWS]

    text = NETLIST.read_text()
    sch = {}
    for blk in re.split(r"\(net\s+\(code", text[text.index("(nets"):])[1:]:
        name = re.search(r'\(name "([^"]*)"', blk).group(1)
        for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"', blk):
            sch[(ref, pin)] = name
    group_net, net_group = {}, {}
    for h, (ref, pin) in sorted(legs.items()):
        g, n = find(h), sch[(ref, pin)]
        if group_net.setdefault(g, n) != n:
            errors.append("%s.%s at %s joins %s and %s" % (ref, pin, h, group_net[g], n))
        if net_group.setdefault(n, g) != g:
            errors.append("net %s is split (at %s.%s, hole %s)" % (n, ref, pin, h))
    expect = {"T:24V": "Net-(J1-24V_IN)", "T:ES+": "/+24V", "T:ES1": "/ES1", "T:ES2": "/ES2",
              "T:L1": "/L1", "T:L2": "/L2", "T:0V": "/GND_24V"}
    for h, name in ends.items():
        if name in expect and group_net.get(find(h)) != expect[name]:
            errors.append("terminal %s at %s is on %s, expected %s" % (name, h, group_net.get(find(h)), expect[name]))
    for hdr, n in (("D2", "/D2"), ("D3", "/D3"), ("D4", "/D4"), ("D5", "/D5"), ("IOREF", "/IOREF"), ("GND", "/GND")):
        if group_net.get(find(("header", hdr))) != n:
            errors.append("header %s is on %s" % (hdr, group_net.get(find(("header", hdr)))))
    # a pad that belongs to no schematic net must not exist (a forgotten or stray run)
    for h in sorted(used):
        if find(h) not in group_net:
            errors.append("hole %s is wired but reaches no part" % (h,))
    if errors:
        sys.exit("PROTOBOARD PLAN IS WRONG:\n  " + "\n  ".join(errors))
    for h in used:
        HOLE_NET[h] = group_net[find(h)]
    return len(net_group)


n_nets = check_against_schematic()

# ----------------------------------------------------------------------------- drawing
P = 2.54                                 # mm per hole


def xy(h):
    return h[1] * P, -h[0] * P


def draw(S, fname, **save):
    """S = drawing scale: 1 for the 1:1 print, 3 for the screen image."""
    fs, lw = 0.75 * S, 0.5 * S           # font and line-width factors
    w_mm, h_mm = (COLS + 5.0) * P, (ROWS + 9.5) * P
    fig = plt.figure(figsize=(S * w_mm / 25.4, S * h_mm / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-2.2 * P, (COLS + 2.8) * P)
    ax.set_ylim(-(ROWS + 5.2) * P, 4.3 * P)
    ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((0.2 * P, -(ROWS + 0.8) * P), (COLS + 0.6) * P, (ROWS + 1.4) * P, fc="#dcefd6", ec="#3a6", lw=0.8 * lw))
    r0, c0, r1, c1 = JACK
    ax.add_patch(Rectangle(((c0 - 0.5) * P, -(r1 + 0.5) * P), (c1 - c0 + 1) * P, (r1 - r0 + 1) * P, fc="#f7d9d9", ec="none"))
    ax.text((c0 + c1) / 2 * P, -(r0 + r1) / 2 * P, "power jack\nbelow:\nno parts", ha="center", va="center", fontsize=3.6 * fs, color="#933")
    a, b = ISOLATION_ROWS
    ax.add_patch(Rectangle((3.5 * P, -(b + 0.5) * P), 14 * P, (b - a + 1) * P, fc="#fff2b3", ec="none"))
    ax.text(2.9 * P, -(a + b) / 2 * P, "isolation\n(keep empty)", ha="right", va="center", fontsize=3.8 * fs)
    for c in range(1, COLS + 1):
        ax.text(c * P, 0.15 * P, str(c), ha="center", va="center", fontsize=4.5 * fs, color="#262")
    for r in range(1, ROWS + 1):
        ax.text(-0.7 * P, -r * P, str(r), ha="right", va="center", fontsize=4.5 * fs, color="#555")
    for h in FREE:
        ax.add_patch(Circle(xy(h), 0.42, fc="white", ec="#9a9", lw=0.3 * lw))
    for h, name in HEADER_LABELS.items():
        ax.add_patch(Circle(xy(h), 0.55, fc="gold", ec="#752", lw=0.3 * lw, zorder=3))
        left = h[1] < 10
        ax.text((h[1] + (-0.8 if left else 0.8)) * P, -h[0] * P, name, ha="right" if left else "left", va="center",
                fontsize=3.8 * fs, weight="bold" if h in HEADER_HOLE.values() else "normal")
    # solder side: bare wires and bridges
    for run in buses:
        xs, ys = zip(*[xy(h) for h in run])
        ax.plot(xs, ys, color="#8a8a8a", lw=2.6 * lw, solid_capstyle="round", zorder=2)
    for p, q in bridges:
        (x1, y1), (x2, y2) = xy(p), xy(q)
        ax.plot([x1, x2], [y1, y2], color="#c9a227", lw=2.6 * lw, solid_capstyle="round", zorder=3)
    # parts
    colour = {"R": "#d9b98a", "LED": "#e03b3b", "D": "#4a90d9", "U": "#333333", "F": "#b33", "C": "#e8a33d"}
    for ref, kind, value, holes in parts:
        pts = [xy(h) for h in holes]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if kind == "U":
            ax.add_patch(FancyBboxPatch((min(xs) - 1.0, min(ys) + 0.9), P + 2.0, max(ys) - min(ys) - 1.8,
                                        boxstyle="round,pad=0.1", fc=colour[kind], ec="k", lw=0.3 * lw, zorder=4))
            ax.add_patch(Circle((xs[0] - 0.5, ys[0] - 1.5), 0.3, fc="white", ec="none", zorder=5))
            ax.text(sum(xs) / 4, sum(ys) / 4, ref, color="white", ha="center", va="center", fontsize=4.5 * fs, zorder=6)
        elif kind == "F":
            ax.add_patch(Circle((sum(xs) / 2, ys[0]), 4.25, fc="#f4c7c7", ec=colour[kind], lw=0.5 * lw, zorder=4, alpha=0.85))
            ax.text(sum(xs) / 2, ys[0] + 1.7, "%s %s" % (ref, value), ha="center", va="center", fontsize=4.2 * fs, zorder=6)
        else:
            ax.plot(xs, ys, color=colour[kind], lw=4.2 * lw, solid_capstyle="round", zorder=4)
            ax.text(sum(xs) / 2, sum(ys) / 2, ref, ha="center", va="center", fontsize=3.3 * fs, zorder=6,
                    color="white" if kind == "D" else "black")
            if kind in ("LED", "D"):           # mark the cathode leg
                kx, ky = xy(holes[0 if kind == "D" else 1])
                ax.text(kx + (1.15 if kind == "LED" else -1.15), ky, "K", ha="left" if kind == "LED" else "right", va="center", fontsize=3.2 * fs, color="#333", zorder=6)
        for p in pts:
            ax.add_patch(Circle(p, 0.42, fc="#222", ec="none", zorder=7))
    # terminals
    for h, name in zip(TERM_HOLES, TERMINALS):
        x, y = xy(h)
        ax.add_patch(Rectangle((x - 0.95 * P, y - 0.6 * P), 1.9 * P, 2.9 * P, fc="#7fd58a", ec="#273", lw=0.4 * lw, zorder=4, alpha=0.9))
        ax.add_patch(Circle((x, y), 0.42, fc="#222", ec="none", zorder=7))
        ax.text(x, y + 1.35 * P, name, ha="center", va="center", fontsize=4.4 * fs, weight="bold", zorder=6)
    ax.text((TERM_HOLES[0][1] + TERM_HOLES[-1][1]) / 2 * P, 4.0 * P, "wires enter from this side (USB end of the Arduino)",
            ha="center", va="center", fontsize=4.2 * fs)
    # where the external 24 V source plugs in
    x24 = TERM_HOLES[TERMINALS.index("24V")][1] * P
    x0v = [h[1] * P for h, n in zip(TERM_HOLES, TERMINALS) if n == "0V"]
    ax.annotate("EXTERNAL 24 V SOURCE:  +", xy=(x24, 2.35 * P), xytext=(x24 - 0.2 * P, 3.15 * P), ha="right", va="center",
                fontsize=4.2 * fs, weight="bold", color="#b00", arrowprops=dict(arrowstyle="->", color="#b00", lw=0.9 * lw))
    ax.annotate("-  (either 0V screw)", xy=(x0v[0], 2.35 * P), xytext=(x0v[0] - 0.4 * P, 3.15 * P), ha="right", va="center",
                fontsize=4.2 * fs, weight="bold", color="#024", arrowprops=dict(arrowstyle="->", color="#024", lw=0.9 * lw))
    # component side: insulated wires
    for a_, b_, col, _ in wires:
        (x1, y1) = xy(a_)
        (x2, y2) = xy(HEADER_HOLE[b_]) if isinstance(b_, str) else xy(b_)
        bend = 0.25 if isinstance(b_, str) else (-0.35 if abs(x2 - x1) < P or abs(y2 - y1) < P else 0.12)
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=8,
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.9 * lw, connectionstyle="arc3,rad=%g" % bend))
        for p in ((x1, y1), (x2, y2)):
            ax.add_patch(Circle(p, 0.3, fc=col, ec="none", zorder=9))
    ax.text(0.2 * P, -(ROWS + 1.3) * P,
            "COMPONENT SIDE, USB end of the Arduino at the top.  Columns = the numbers printed on the board.\n"
            "Row 1 = the row next to those numbers.  Yellow = solder bridge (solder side).\n"
            "Grey = bare wire soldered along the pads (solder side).  Thin coloured = insulated wire.\n"
            "Resistors and 1N4148 stand upright in two neighbouring holes; R1-R4 are 1/2 W.\n"
            "K = cathode (short LED leg, diode band).  White dot = PC817 pin 1.  Gold = pad joined to a header pin.",
            ha="left", va="top", fontsize=4.0 * fs)
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / fname, **save)
    plt.close(fig)


def main():
    if plt is None:
        sys.exit("matplotlib is needed for the drawing")
    draw(1, "layout.pdf")                 # prints at 1:1
    draw(3, "layout.png", dpi=110)        # for the screen

    def hole(h):
        return "row %d, col %d" % h

    lines = ["# Proto-shield build plan", "",
             "For the green ElectroCookie *Uno ProtoShield Universal*. Generated by `generate_protoboard.py`.",
             "The plan was checked against the schematic: the holes it joins form the same %d nets as the" % n_nets,
             "KiCad netlist, and every hole it uses exists on the board as mapped in the script.", "",
             "![Layout](layout.png)", "",
             "## How holes are named", "",
             "- Look at the **component side**, with the Arduino's USB end at the top.",
             "- **Columns 1-20** are the numbers printed along the top edge.",
             "- **Row 1** is the row next to those numbers; rows count downwards to 25.",
             "- `layout.pdf` prints at 1:1 at 100 % scale.",
             "- Rows %d and %d stay empty: they are the isolation gap under the optocouplers." % ISOLATION_ROWS,
             "- Rows 1-5 of columns 2-5 are above the Arduino's power jack: nothing is soldered there.",
             "", "## 1. Parts", "", "| Part | Value | Holes | Note |", "|---|---|---|---|"]
    note = {"R": "stands upright; body on the first hole", "LED": "first hole = anode (long leg)",
            "D": "stands upright; first hole = cathode (band)", "U": "holes in pin order 1, 2, 3, 4; pin 1 = dot",
            "F": "", "C": "optional; either way round"}
    for ref, kind, value, holes in parts:
        lines.append("| %s | %s | %s | %s |" % (ref, value, "; ".join(hole(h) for h in holes), note[kind]))
    lines += ["", "Screw terminals, 5.08 mm pitch, along row 1, wire entry towards the top edge:", "",
              "| Terminal | Hole |", "|---|---|"]
    for h, name in zip(TERM_HOLES, TERMINALS):
        lines.append("| `%s` | %s |" % (name, hole(h)))
    lines += ["", "### What plugs into each screw", "",
              "| Screw | Connect |", "|---|---|",
              "| `24V` | **plus of the external 24 V source** |",
              "| `0V` (either) | **minus of the external 24 V source**; also the lidars' 0 V |",
              "| `ES+` | one terminal of each e-stop button (fused 24 V going out) |",
              "| `ES1`, `ES2` | the other terminal of button 1, of button 2 |",
              "| `L1`, `L2` | safety output of lidar 1, of lidar 2 |", "",
              "The board has no 24 V source of its own and draws about 13 mA. Never join `0V` to the Arduino's `GND`."]
    lines += ["", "## 2. Solder side: bridges between neighbouring pads", "", "| From | To |", "|---|---|"]
    for p, q in bridges:
        lines.append("| %s | %s |" % (hole(p), hole(q)))
    lines += ["", "## 3. Solder side: bare wire along a line of pads", "", "| From | Through | To |", "|---|---|---|"]
    for b in buses:
        corners = [b[0]] + [b[i] for i in range(1, len(b) - 1)
                            if (b[i][0] - b[i - 1][0], b[i][1] - b[i - 1][1]) != (b[i + 1][0] - b[i][0], b[i + 1][1] - b[i][1])] + [b[-1]]
        lines.append("| %s | %s | %s |" % (hole(corners[0]), "; ".join(hole(h) for h in corners[1:-1]) or "straight", hole(corners[-1])))
    lines += ["", "## 4. Component side: insulated wires", "", "| From | To | Purpose |", "|---|---|---|"]
    for p, q, _, why in wires:
        to = "header pad **%s** (%s)" % (q, hole(HEADER_HOLE[q])) if isinstance(q, str) else hole(q)
        lines.append("| %s | %s | %s |" % (hole(p), to, why))
    lines += ["", "## 5. Checked on the real board (2026-10-05)", "",
              "1. Pad count matches the drawing: 20 columns in rows 1-4, 14 columns (4 to 17) in rows 11-25.",
              "2. Each inner pad beside a header pin is joined to that pin (multimeter).",
              "3. The 24V terminal pin at column 6 clears the Arduino's power jack.",
              "", "## 6. Before applying 24 V", "",
              "1. No continuity between any `0V` terminal and the Arduino `GND` pin.",
              "2. No continuity between the `24V` or `ES+` terminal and any header pin.",
              "3. Diode test across each PC817 pins 1-2: a reading one way (LED), about 0.6 V the other (1N4148).",
              "4. Fuse fitted; `24V` to `ES+` reads near 0 Ω.", ""]
    (OUT / "BUILD.md").write_text("\n".join(lines))
    print("written: protoboard/layout.png, layout.pdf, BUILD.md (%d parts, %d bridges, %d bare-wire runs, %d wires; %d nets match the schematic)"
          % (len(parts), len(bridges), len(buses), len(wires), n_nets))


if __name__ == "__main__":
    main()
