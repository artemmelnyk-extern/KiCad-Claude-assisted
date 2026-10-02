#!/usr/bin/env bash
# Regenerate the KiCad files, run KiCad's electrical rule check, export PDF + SVG.
# Needs kicad-cli and KiCad's Python (module pcbnew), KiCad 9 or later. With the Flatpak build:
#   KICAD_CLI="flatpak run --command=kicad-cli --filesystem=$PWD org.kicad.KiCad" \
#   KICAD_PYTHON="flatpak run --command=python3 --filesystem=$PWD org.kicad.KiCad" ./check.sh
set -euo pipefail
cd "$(dirname "$0")"
KICAD_CLI=${KICAD_CLI:-kicad-cli}
KICAD_PYTHON=${KICAD_PYTHON:-python3}
PLOT_PYTHON=${PLOT_PYTHON:-python3}      # any Python 3 with matplotlib

SCH=kicad/pc817_bench.kicad_sch
PCB=kicad/pc817_bench.kicad_pcb

python3 generate.py
$KICAD_CLI sch erc --severity-all --exit-code-violations -o erc.rpt $SCH
$KICAD_CLI sch export netlist -o kicad/pc817_bench.net $SCH
$PLOT_PYTHON generate_protoboard.py   # build plan, checked against the netlist (needs matplotlib)
$KICAD_PYTHON generate_pcb.py      # KiCad model of the build plan
# The model is not a board to manufacture, so the usual pass/fail does not apply:
#  - each insulated wire is an "unconnected" item (they are not copper), plus one for the
#    two GND header pins, which only the Arduino joins;
#  - upright parts in neighbouring holes overlap each other's courtyard by design.
# What must hold: the board matches the schematic, and nothing else is an error.
$KICAD_CLI pcb drc --schematic-parity --severity-all -o drc.rpt $PCB
python3 - <<'PY'
import re, sys
t = open("drc.rpt").read()
kinds = re.findall(r"^\[(\w+)\]: .*\n\s+(?:Rule|Local)[^;]*; (\w+)", t, re.M)
errors = sorted({k for k, sev in kinds if sev == "error"} - {"courtyards_overlap", "pth_inside_courtyard", "unconnected_items"})
unconnected = sum(1 for k, _ in kinds if k == "unconnected_items")
parity = int(re.search(r"Found (\d+) Footprint errors", t).group(1))
wires = len(re.findall(r"^\| row .* \| .* \| (?:output|input|logic|fused)", open("protoboard/BUILD.md").read(), re.M))
ok = not errors and parity == 0 and unconnected == wires + 1
print("model check: %d wires, %d unconnected items (expected %d), parity issues %d, other errors %s"
      % (wires, unconnected, wires + 1, parity, errors or "none"))
sys.exit(0 if ok else 1)
PY

$KICAD_CLI sch export pdf -o docs/pc817_bench.pdf $SCH
$KICAD_CLI sch export svg -o docs $SCH
$KICAD_CLI pcb export svg -o docs/pcb_layout.svg --layers "F.Cu,B.Cu,F.SilkS,Edge.Cuts" \
    --mode-single --page-size-mode 2 --exclude-drawing-sheet $PCB
$KICAD_CLI pcb render -o docs/pcb_3d_top.png -w 1400 --height 1000 --side top --background opaque $PCB
echo "OK: schematic checked, build plan and its KiCad model match the schematic, docs/ updated"
