#!/usr/bin/env bash
# Regenerate the KiCad files, run KiCad's electrical rule check, export PDF + SVG.
# Needs kicad-cli (KiCad 8 or later). With the Flatpak build, set:
#   KICAD_CLI="flatpak run --command=kicad-cli --filesystem=$PWD org.kicad.KiCad"
set -euo pipefail
cd "$(dirname "$0")"
KICAD_CLI=${KICAD_CLI:-kicad-cli}

python3 generate.py
$KICAD_CLI sch erc --severity-all --exit-code-violations -o erc.rpt kicad/pc817_bench.kicad_sch
$KICAD_CLI sch export pdf -o docs/pc817_bench.pdf kicad/pc817_bench.kicad_sch
$KICAD_CLI sch export svg -o docs kicad/pc817_bench.kicad_sch
echo "OK: rule check passed, docs/ updated"
