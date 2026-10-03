#!/usr/bin/env python3
"""Proto-shield build plan: the same circuit on a 2.54 mm grid of isolated pads.

Writes protoboard/layout.png, protoboard/layout.pdf (1:1 when printed at 100 %) and
protoboard/BUILD.md (hole-by-hole tables). Before writing, it checks that the holes joined
by the plan form exactly the nets of the KiCad schematic (kicad/pc817_bench.net).

Needs matplotlib. Run: python3 generate_protoboard.py   (after generate.py + netlist export)

Grid: row 0 at the top, column 0 at the left, seen from the COMPONENT side.
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

ROWS, COLS = 16, 17
C = 3                                   # first column of a channel
BUS_24V_RET = 2                         # column of the 0V (24 V side) bus
IOREF_COL = C + 13

# channel: (schematic number, first row, input name, Arduino pin, resistor value)
CHANNELS = [(1, 3, "ES1", "D2", "1.5k"), (2, 6, "ES2", "D3", "1.5k"),
            (3, 9, "L1", "D4", "2.2k"), (4, 12, "L2", "D5", "2.2k")]
# screw terminals in column 0, one every 2 rows (5.08 mm blocks)
TERMINALS = ["24V", "ES+", "ES1", "ES2", "L1", "L2", "0V", "0V"]
TERM_ROW = {i: 2 * i for i in range(len(TERMINALS))}

legs = {}        # (row, col) -> (ref, pin)        part legs
ends = {}        # (row, col) -> name              terminals and wire landings
parts = []       # (ref, kind, value, [(row, col), ...])
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


for ch, r, name, pin, rval in CHANNELS:
    part("R%d" % (2 * ch - 1), "R", rval, [("1", (r, C + 1)), ("2", (r, C + 2))])
    part("R%d" % (2 * ch), "R", rval, [("1", (r, C + 3)), ("2", (r, C + 4))])
    part("D%d" % ch, "LED", "LED", [("2", (r, C + 5)), ("1", (r, C + 6))])            # 2 = anode
    part("D%d" % (ch + 4), "D", "1N4148", [("1", (r + 1, C + 5)), ("2", (r + 1, C + 4))])   # 1 = cathode; body away from the LED
    part("U%d" % ch, "U", "PC817", [("1", (r, C + 7)), ("2", (r + 1, C + 7)),
                                    ("3", (r + 1, C + 10)), ("4", (r, C + 10))])
    part("R%d" % (ch + 8), "R", "10k", [("2", (r, C + 11)), ("1", (r, C + 12))])
    # optional filter capacitor, in the two spare rows above the channel: output side next to
    # the output wire landing, GND side next to the GND landing of the channel above
    part("C%d" % ch, "C", "100n opt.", [("1", (r - 1, C + 12)), ("2", (r - 2, C + 12))])
    bridge((r - 1, C + 11), (r - 1, C + 12))        # output landing -> capacitor
    bridge((r - 2, C + 11), (r - 2, C + 12))        # GND landing above -> capacitor
    bridge((r, C + 12), (r, C + 13))                # pull-up -> IOREF bus
    ends[(r, C)] = "%s in" % name
    ends[(r - 1, C + 11)] = "%s out" % pin
    ends[(r + 1, C + 11)] = "GND"
    bridge((r, C), (r, C + 1))                      # input wire -> first resistor
    bridge((r, C + 2), (r, C + 3))                  # resistor 1 -> resistor 2
    bridge((r, C + 4), (r, C + 5))                  # resistor 2 -> LED anode
    bridge((r, C + 5), (r + 1, C + 5))              # LED anode -> diode cathode
    bridge((r, C + 6), (r, C + 7))                  # LED cathode -> optocoupler pin 1
    bridge((r + 1, C + 4), (r + 2, C + 4))          # diode anode -> 0V strip below
    bridge((r, C + 10), (r, C + 11))                # collector -> pull-up
    bridge((r - 1, C + 11), (r, C + 11))            # ... -> output wire landing
    bridge((r + 1, C + 10), (r + 1, C + 11))        # emitter -> GND wire landing
    # 0V strip in the spare row under the channel, back to the bus column
    buses.append([(r + 1, C + 7), (r + 2, C + 7)] + [(r + 2, c) for c in range(C + 6, BUS_24V_RET - 1, -1)])   # from optocoupler pin 2
    wires.append(((r - 1, C + 11), pin, "tab:blue", "output"))

# fuse on the incoming 24 V, top row
part("F1", "F", "T2A", [("1", (1, 4)), ("2", (1, 6))])       # clear of the terminal block and of the header above
buses.append([(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 4)])  # 24V terminal -> fuse
ends[(1, 7)] = "24V fused"
bridge((1, 6), (1, 7))
ends[(2, 1)] = "ES+"
bridge((2, 1), (2, 0))
wires.append(((1, 7), (2, 1), "tab:red", "fused 24 V to the ES+ terminal"))

for i, name in enumerate(TERMINALS):
    ends[(TERM_ROW[i], 0)] = "T:" + name
# inputs: terminal -> landing next to it -> wire to the channel
for ch, r, name, pin, rval in CHANNELS:
    tr = TERM_ROW[TERMINALS.index(name)]
    ends[(tr, 1)] = name
    bridge((tr, 0), (tr, 1))
    wires.append(((tr, 1), (r, C), "tab:orange", "input"))
# 0V bus down column 2, joined to both 0V terminals
first_strip = CHANNELS[0][1] + 2
buses.append([(r, BUS_24V_RET) for r in range(first_strip, ROWS)])
for i, name in enumerate(TERMINALS):
    if name == "0V":
        buses.append([(TERM_ROW[i], 0), (TERM_ROW[i], 1), (TERM_ROW[i], 2)])
# IOREF bus down the last column
buses.append([(r, IOREF_COL) for r in range(CHANNELS[0][1], CHANNELS[-1][1] + 2)])
ends[(CHANNELS[-1][1] + 1, IOREF_COL)] = "IOREF"
wires.append(((CHANNELS[-1][1] + 1, IOREF_COL), "IOREF", "tab:purple", "logic supply reference"))
# logic GND: daisy chain, then to the header
gnd = [(r + 1, C + 11) for _, r, _, _, _ in CHANNELS]
gnd.insert(0, (CHANNELS[0][1] - 2, C + 11))         # GND pad for the first channel's capacitor
ends[gnd[0]] = "GND"
for a, b in zip(gnd, gnd[1:]):
    wires.append((a, b, "black", "logic GND"))
wires.append((gnd[-1], "GND", "black", "logic GND"))


# ----------------------------------------------------------------------------- check
HOLE_NET = {}       # (row, col) -> schematic net name, for every pad the plan uses


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

    for a, b in bridges:
        union(a, b)
    for b in buses:
        for x, y in zip(b, b[1:]):
            assert abs(x[0] - y[0]) + abs(x[1] - y[1]) == 1, "bus not contiguous: %s %s" % (x, y)
            union(x, y)
    for a, b, _, _ in wires:
        union(a, ("header", b) if isinstance(b, str) else b)
    # a pad may be used by one thing only (leg, landing or bus pad of ONE net)
    used = {}
    for b in buses:
        for h in b:
            used.setdefault(h, set()).add(find(h))
    for h, nets in used.items():
        assert len(nets) == 1, "two buses of different nets on pad %s" % (h,)

    text = NETLIST.read_text()
    sch = {}
    for blk in re.split(r"\(net\s+\(code", text[text.index("(nets"):])[1:]:
        name = re.search(r'\(name "([^"]*)"', blk).group(1)
        for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"', blk):
            sch[(ref, pin)] = name
    group_net, net_group, errors = {}, {}, []
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
    if errors:
        sys.exit("PROTOBOARD PLAN DOES NOT MATCH THE SCHEMATIC:\n  " + "\n  ".join(errors))
    for h in list(parent):
        if isinstance(h[0], int):
            HOLE_NET[h] = group_net.get(find(h))
    return len(net_group)


n_nets = check_against_schematic()

# ----------------------------------------------------------------------------- drawing
P = 2.54                                 # mm per hole


def xy(h):
    return h[1] * P, -h[0] * P


def draw(S, fname, **save):
    """S = drawing scale: 1 for the 1:1 print, 3 for the screen image."""
    fs, lw = 0.75 * S, 0.5 * S           # font and line-width factors
    w_mm, h_mm = (COLS + 10.5) * P, (ROWS + 5.0) * P
    fig = plt.figure(figsize=(S * w_mm / 25.4, S * h_mm / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-2.6 * P, (COLS + 7.9) * P)
    ax.set_ylim(-(ROWS + 3.2) * P, 1.8 * P)
    ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((-0.5 * P, -(ROWS - 0.5) * P), COLS * P, ROWS * P, fc="#e9f3e4", ec="#557", lw=0.6 * lw))
    ax.add_patch(Rectangle(((C + 7.6) * P, -(ROWS - 0.5) * P), 1.8 * P, ROWS * P, fc="#fff2b3", ec="none"))
    ax.text((C + 8.5) * P, -(ROWS - 0.2) * P, "isolation gap\n(keep empty)", ha="center", va="top", fontsize=4.2 * fs)
    for r in range(ROWS):
        ax.text(-1.9 * P, -r * P, str(r), ha="right", va="center", fontsize=4.5 * fs, color="#555")
        for c in range(COLS):
            ax.add_patch(Circle(xy((r, c)), 0.42, fc="white", ec="#9a9", lw=0.3 * lw))
    for c in range(COLS):
        ax.text(c * P, 1.1 * P, str(c), ha="center", va="center", fontsize=4.5 * fs, color="#555")
    # solder side: buses and bridges
    for b in buses:
        xs, ys = zip(*[xy(h) for h in b])
        ax.plot(xs, ys, color="#8a8a8a", lw=2.6 * lw, solid_capstyle="round", zorder=2)
    for a, b in bridges:
        (x1, y1), (x2, y2) = xy(a), xy(b)
        ax.plot([x1, x2], [y1, y2], color="#c9a227", lw=2.6 * lw, solid_capstyle="round", zorder=3)
    # parts
    colour = {"R": "#d9b98a", "LED": "#e03b3b", "D": "#4a90d9", "U": "#333333", "F": "#b33", "C": "#e8a33d"}
    for ref, kind, value, holes in parts:
        pts = [xy(h) for h in holes]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if kind == "U":
            ax.add_patch(FancyBboxPatch((min(xs) + 0.9, min(ys) - 1.0), max(xs) - min(xs) - 1.8, P + 2.0,
                                        boxstyle="round,pad=0.1", fc=colour[kind], ec="k", lw=0.3 * lw, zorder=4))
            ax.add_patch(Circle((min(xs) + 1.6, max(ys) + 0.4), 0.3, fc="white", ec="none", zorder=5))
            ax.text(sum(xs) / 4, sum(ys) / 4, ref, color="white", ha="center", va="center", fontsize=4.5 * fs, zorder=6)
        elif kind == "F":
            ax.add_patch(Circle((sum(xs) / 2, ys[0]), 4.25, fc="#f4c7c7", ec=colour[kind], lw=0.5 * lw, zorder=4))
            ax.text(sum(xs) / 2, ys[0] + 1.6, "%s %s" % (ref, value), ha="center", va="center", fontsize=4.5 * fs, zorder=6)
        else:
            ax.plot(xs, ys, color=colour[kind], lw=4.2 * lw, solid_capstyle="round", zorder=4)
            label = ref if kind != "R" else "%s\n%s" % (ref, value)
            ax.text(sum(xs) / 2, sum(ys) / 2, label, ha="center", va="center", fontsize=3.3 * fs, zorder=6,
                    color="white" if kind == "D" else "black", linespacing=0.9)
            if kind in ("LED", "D"):           # mark the cathode leg
                k = xy(holes[0 if kind == "D" else 1])
                ax.text(k[0], k[1] + 1.05, "K", ha="center", va="bottom", fontsize=3.4 * fs, color="#333", zorder=6)
        for p in pts:
            ax.add_patch(Circle(p, 0.42, fc="#222", ec="none", zorder=7))
    # terminals
    for i, name in enumerate(TERMINALS):
        x, y = xy((TERM_ROW[i], 0))
        ax.add_patch(Rectangle((x - 1.75 * P, y - 0.95 * P), 2.25 * P, 1.9 * P, fc="#7fd58a", ec="#273", lw=0.4 * lw, zorder=4))
        ax.add_patch(Circle((x, y), 0.42, fc="#222", ec="none", zorder=7))
        ax.text(x - 0.75 * P, y, name, ha="center", va="center", fontsize=5 * fs, weight="bold", zorder=6)
    # component side: insulated wires
    header_x = (COLS + 0.9) * P
    header_rows = {"D2": 2, "D3": 4, "D4": 6, "D5": 8, "GND": 13, "IOREF": 15}
    for name, r in header_rows.items():
        ax.text(header_x + 0.5 * P, -r * P, "to header pin\n%s" % name, ha="left", va="center", fontsize=4.6 * fs, weight="bold")
        ax.add_patch(Circle((header_x, -r * P), 0.5, fc="gold", ec="k", lw=0.3 * lw, zorder=7))
    for a, b, col, _ in wires:
        (x1, y1) = xy(a)
        (x2, y2) = (header_x, -header_rows[b] * P) if isinstance(b, str) else xy(b)
        bend = 0.18 if abs(x2 - x1) > P else -0.45     # same-column wires bow to the right
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=8,
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.9 * lw, connectionstyle="arc3,rad=%g" % bend))
        for p in ((x1, y1), (x2, y2)):
            ax.add_patch(Circle(p, 0.3, fc=col, ec="none", zorder=9))
    ax.text(-2.0 * P, -(ROWS + 1.3) * P,
            "COMPONENT SIDE.  Yellow = solder bridge between two pads (solder side).\n"
            "Grey = bare wire soldered along the pads (solder side).  Thin coloured = insulated wire.\n"
            "Resistors and 1N4148 stand upright in two neighbouring holes.\n"
            "K = cathode (short LED leg, diode band).  White dot = PC817 pin 1.\n"
            "The fuse body (8.5 mm) covers rows 0-2 around columns 4-6.",
            ha="left", va="top", fontsize=4.4 * fs)
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / fname, **save)
    plt.close(fig)


def main():
    if plt is None:
        sys.exit("matplotlib is needed for the drawing")
    draw(1, "layout.pdf")                 # prints at 1:1
    draw(3, "layout.png", dpi=110)        # for the screen


    # ----------------------------------------------------------------------------- build sheet
    def hole(h):
        return "row %d, col %d" % h


    lines = ["# Proto-shield build plan", "",
             "Generated by `generate_protoboard.py`. The plan was checked against the schematic: the holes",
             "it joins form the same %d nets as the KiCad netlist." % n_nets, "",
             "![Layout](layout.png)", "",
             "- Needs a grid of **%d rows × %d columns of isolated pads** (%.0f × %.0f mm)." % (ROWS, COLS, ROWS * P, COLS * P),
             "- Rows and columns are counted from 0, top-left, seen from the **component side**.",
             "- `layout.pdf` prints at 1:1 at 100 % scale.",
             "- Columns %d and %d stay empty: they are the isolation gap under the optocouplers." % (C + 8, C + 9),
             "", "## 1. Parts", "", "| Part | Value | Holes | Note |", "|---|---|---|---|"]
    note = {"R": "stands upright", "LED": "first hole = anode (long leg)", "D": "stands upright; first hole = cathode (band)",
            "U": "holes in pin order 1, 2, 3, 4; pin 1 = dot", "F": "", "C": "optional; either way round"}
    for ref, kind, value, holes in parts:
        lines.append("| %s | %s | %s | %s |" % (ref, value, "; ".join(hole(h) for h in holes), note[kind]))
    lines += ["", "Screw terminals, 5.08 mm pitch, in column 0:", "", "| Terminal | Hole |", "|---|---|"]
    for i, name in enumerate(TERMINALS):
        lines.append("| `%s` | %s |" % (name, hole((TERM_ROW[i], 0))))
    lines += ["", "## 2. Solder side: bridges between neighbouring pads", "", "| From | To |", "|---|---|"]
    for a, b in bridges:
        lines.append("| %s | %s |" % (hole(a), hole(b)))
    lines += ["", "## 3. Solder side: bare wire along a line of pads", "", "| From | Through | To |", "|---|---|---|"]
    for b in buses:
        corners = [b[0]] + [b[i] for i in range(1, len(b) - 1)
                            if (b[i][0] - b[i - 1][0], b[i][1] - b[i - 1][1]) != (b[i + 1][0] - b[i][0], b[i + 1][1] - b[i][1])] + [b[-1]]
        lines.append("| %s | %s | %s |" % (hole(corners[0]), "; ".join(hole(h) for h in corners[1:-1]) or "straight", hole(corners[-1])))
    lines += ["", "## 4. Component side: insulated wires", "", "| From | To | Purpose |", "|---|---|---|"]
    for a, b, _, why in wires:
        lines.append("| %s | %s | %s |" % (hole(a), "header pin **%s**" % b if isinstance(b, str) else hole(b), why))
    lines += ["", "## 5. Before applying 24 V", "",
              "1. No continuity between any `0V` terminal and the Arduino `GND` pin.",
              "2. No continuity between the `24V` or `ES+` terminal and any header pin.",
              "3. Diode test across each PC817 pins 1-2: a reading one way (LED), about 0.6 V the other (1N4148).",
              "4. Fuse fitted; `24V` to `ES+` reads near 0 Ω.", ""]
    (OUT / "BUILD.md").write_text("\n".join(lines))
    print("written: protoboard/layout.png, layout.pdf, BUILD.md (%d parts, %d bridges, %d bare-wire runs, %d wires; %d nets match the schematic)"
          % (len(parts), len(bridges), len(buses), len(wires), n_nets))


if __name__ == "__main__":
    main()
