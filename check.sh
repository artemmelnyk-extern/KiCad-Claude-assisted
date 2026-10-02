#!/usr/bin/env bash
# Regenerate the KiCad files, run KiCad's electrical rule check, export PDF + SVG.
# Needs kicad-cli and KiCad's Python (module pcbnew), KiCad 9 or later. With the Flatpak build:
#   KICAD_CLI="flatpak run --command=kicad-cli --filesystem=$PWD org.kicad.KiCad" \
#   KICAD_PYTHON="flatpak run --command=python3 --filesystem=$PWD org.kicad.KiCad" ./check.sh
set -euo pipefail
cd "$(dirname "$0")"
KICAD_CLI=${KICAD_CLI:-kicad-cli}
KICAD_PYTHON=${KICAD_PYTHON:-python3}

SCH=kicad/pc817_bench.kicad_sch
PCB=kicad/pc817_bench.kicad_pcb

python3 generate.py
$KICAD_CLI sch erc --severity-all --exit-code-violations -o erc.rpt $SCH
$KICAD_CLI sch export netlist -o kicad/pc817_bench.net $SCH
$KICAD_PYTHON generate_pcb.py
# lib_footprint_mismatch is expected: the Arduino footprint is flipped and stripped of its courtyard
$KICAD_CLI pcb drc --schematic-parity --severity-error --exit-code-violations -o drc.rpt $PCB

$KICAD_CLI sch export pdf -o docs/pc817_bench.pdf $SCH
$KICAD_CLI sch export svg -o docs $SCH
$KICAD_CLI pcb export svg -o docs/pcb_layout.svg --layers "F.Cu,B.Cu,F.SilkS,Edge.Cuts" \
    --mode-single --page-size-mode 2 --exclude-drawing-sheet $PCB
$KICAD_CLI pcb render -o docs/pcb_3d_top.png -w 1400 --height 1000 --side top --background opaque $PCB
python3 generate_protoboard.py     # proto-shield plan, checked against the netlist (needs matplotlib)
echo "OK: schematic and board rule checks passed, docs/ updated"
