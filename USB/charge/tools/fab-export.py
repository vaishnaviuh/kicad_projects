#!/usr/bin/env python3
"""
fab-export.py — generate fab-ready outputs for the USB-A and USB-C charger boards.


Produces, under <project>/fab_output/:
  1. <name>-bom.csv            BOM (no MPN field in these schematics — Value/Footprint based)
  2. <name>-pos.csv            pick-and-place (both sides, mm)
  3. fab_output/gerbers/*.gbr  Gerbers (4-layer: F/In1/In2/B + mask/silk/paste/edge)
  4. fab_output/gerbers/*.drl  Excellon drill files + drill map
  5. <name>-fab-<ts>.zip       single archive of the fab_output/ tree

IMPORTANT — zone fills: the `kicadfills` clean filter (USB/tools/
kicad-strip-fills.py) strips computed `(filled_polygon ...)` from committed
boards, so a fresh checkout has EMPTY pours. Open the board in pcbnew, press B
(Fill All Zones), and save before exporting — otherwise the copper pours are
missing from the Gerbers. This script refuses to run on a board that has zones
but no fills.

Re-runnable: outputs are overwritten in place. Run from any working directory.
Requires kicad-cli (KiCad >= 8).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

CHARGE = Path(__file__).resolve().parent.parent

FAB_LAYERS = (
    "F.Cu,In1.Cu,In2.Cu,B.Cu,"
    "F.Paste,B.Paste,F.Mask,B.Mask,"
    "F.SilkS,B.SilkS,Edge.Cuts"
)

PROJECTS = [
    {
        "name": "USB_A",
        "dir": CHARGE / "USB-A",
        "pcb": "USB_A.kicad_pcb",
        "sch": "USB_A.kicad_sch",
        "layers": FAB_LAYERS,
    },
    {
        "name": "USB_C",
        "dir": CHARGE / "USB_C",
        "pcb": "USB_C.kicad_pcb",
        "sch": "USB_C.kicad_sch",
        "layers": FAB_LAYERS,
    },
]


def run(cmd: list[str]) -> None:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {cmd[0]}")
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            print(f"    {line}")


def assert_filled(proj: dict) -> None:
    """Refuse to export a board whose zones were stripped by the clean filter."""
    text = (proj["dir"] / proj["pcb"]).read_text()
    has_zones = re.search(r"\(zone\s", text) is not None
    n_fills = text.count("(filled_polygon")
    if has_zones and n_fills == 0:
        raise SystemExit(
            f"  {proj['pcb']}: zones present but UNFILLED (0 filled polygons).\n"
            "  The kicadfills clean filter strips fills from committed boards.\n"
            "  Open the board in pcbnew, press B (Fill All Zones), save, then re-run —\n"
            "  exporting now would produce Gerbers with MISSING copper pours."
        )


def export_bom(proj: dict) -> Path:
    fab = proj["dir"] / "fab_output"
    fab.mkdir(parents=True, exist_ok=True)
    out = fab / f"{proj['name']}-bom.csv"
    sch = proj["dir"] / proj["sch"]
    # These schematics carry no MPN field; group by Value+Footprint instead.
    run([
        "kicad-cli", "sch", "export", "bom",
        "--output", str(out),
        "--fields",
        "Reference,${QUANTITY},Value,${DNP},${EXCLUDE_FROM_BOM},${EXCLUDE_FROM_BOARD},Footprint,Datasheet,Description",
        "--labels",
        "Reference,Qty,Value,DNP,Exclude from BOM,Exclude from Board,Footprint,Datasheet,Description",
        "--group-by", "Value,Footprint",
        "--ref-range-delimiter", "",  # list refs individually, no C1-C5 ranges
        "--exclude-dnp",
        str(sch),
    ])
    return out


def export_pos(proj: dict) -> Path:
    fab = proj["dir"] / "fab_output"
    fab.mkdir(parents=True, exist_ok=True)
    out = fab / f"{proj['name']}-pos.csv"
    pcb = proj["dir"] / proj["pcb"]
    run([
        "kicad-cli", "pcb", "export", "pos",
        "--output", str(out),
        "--format", "csv",
        "--units", "mm",
        "--side", "both",
        "--use-drill-file-origin",
        "--exclude-dnp",
        str(pcb),
    ])
    return out


def filter_pos(pos_file: Path) -> None:
    """Drop mounting holes from the pick-and-place file.

    Update-PCB-from-Schematic rebuilds footprint attributes from the
    schematic, which has no exclude-from-position-files concept, so the
    flag on mounting holes is silently wiped by every F8 import. Filter
    them here so the POS never contains non-placeable parts regardless
    of the board file's attribute state.
    """
    import csv

    rows = list(csv.reader(pos_file.open()))
    keep = [r for r in rows if not (len(r) > 2 and "MountingHole" in r[2])]
    dropped = len(rows) - len(keep)
    if dropped:
        with pos_file.open("w", newline="") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerows(keep)
        print(f"    filtered {dropped} mounting hole(s) from {pos_file.name}")


def export_gerbers(proj: dict) -> Path:
    out_dir = proj["dir"] / "fab_output" / "gerbers"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*"):
        stale.unlink()  # renamed outputs must not leave stale files for the zip
    pcb = proj["dir"] / proj["pcb"]
    run([
        "kicad-cli", "pcb", "export", "gerbers",
        "--output", str(out_dir) + "/",
        "--layers", proj["layers"],
        "--use-drill-file-origin",
        "--no-protel-ext",
        str(pcb),
    ])
    return out_dir


def linearize_profile(gerber_dir: Path) -> None:
    """Replace G02/G03 arcs in ALL plotted gerbers with chord segments.

    Some fab DFM/preview/CAM engines mis-handle G75 multi-quadrant arcs
    (rendering pie wedges or taking the complementary sweep), which breaks the
    board outline. Lines-only profiles parse correctly everywhere. Chord
    sagitta is kept under ~2 um so the contour is fab-identical.
    """
    import math

    for gbr in sorted(gerber_dir.glob("*.gbr")):
        lines = gbr.read_text().splitlines()
        out, cur, mode = [], (None, None), "G01"
        arc_dir = 0  # +1 = G03 (CCW in gerber Y-up), -1 = G02
        n_arcs = 0
        coord = re.compile(
            r"^X(-?\d+)Y(-?\d+)(?:I(-?\d+)J(-?\d+))?D0([12])\*$")
        for ln in lines:
            if ln in ("G75*",):
                continue  # multi-quadrant mode marker no longer needed
            if ln in ("G01*", "G02*", "G03*"):
                mode = ln[:3]
                arc_dir = {"G01": 0, "G02": -1, "G03": 1}[mode]
                if mode == "G01":
                    out.append(ln)
                continue
            m = coord.match(ln)
            if not m:
                out.append(ln)
                continue
            x, y = int(m.group(1)), int(m.group(2))
            if m.group(5) == "2" or arc_dir == 0 or m.group(3) is None:
                out.append(ln)
                cur = (x, y)
                continue
            # arc D01 with I/J center offset, units = gerber int (1e-6 mm)
            n_arcs += 1
            i, j = int(m.group(3)), int(m.group(4))
            cx, cy = cur[0] + i, cur[1] + j
            r = math.hypot(cur[0] - cx, cur[1] - cy)
            a0 = math.atan2(cur[1] - cy, cur[0] - cx)
            a1 = math.atan2(y - cy, x - cx)
            sweep = (a1 - a0) % (2 * math.pi)
            if arc_dir < 0:
                sweep = sweep - 2 * math.pi
            if abs(sweep) < 1e-9:
                sweep = arc_dir * 2 * math.pi  # full circle
            # chord count for <2um sagitta
            n = max(8, int(abs(sweep) / (2 * math.acos(max(0.0, 1 - 2000 / r))))
                    ) if r > 2000 else 8
            for k in range(1, n + 1):
                if k == n:
                    px, py = x, y  # exact original arc endpoint
                else:
                    a = a0 + sweep * k / n
                    px = round(cx + r * math.cos(a))
                    py = round(cy + r * math.sin(a))
                out.append(f"X{px}Y{py}D01*")
            out.append("G01*")
            cur = (x, y)
        gbr.write_text("\n".join(out) + "\n")
        if n_arcs:
            print(f"    linearized {n_arcs} arc(s) in {gbr.name}")


def reorder_profile(gerber_dir: Path) -> None:
    """Rewrite the Profile gerber as one contiguous closed loop.

    KiCad plots outline primitives in arbitrary order with pen-up moves
    between them; naive preview renderers that fill vertices in file order
    draw crossing edges through the board. Chaining the segments head-to-
    tail (reversing where needed) makes the path unambiguous for any parser.
    """
    for gbr in gerber_dir.glob("*Edge_Cuts.gbr"):
        lines = gbr.read_text().splitlines()
        head, segs, cur, tail = [], [], None, []
        coord = re.compile(r"^X(-?\d+)Y(-?\d+)D0([12])\*$")
        for ln in lines:
            m = coord.match(ln)
            if not m:
                (tail if ln == "M02*" else head).append(ln)
                continue
            x, y, d = int(m.group(1)), int(m.group(2)), m.group(3)
            if d == "1" and cur is not None:
                segs.append((cur, (x, y)))
            cur = (x, y)
        # chain segments into one loop
        near = lambda p, q: abs(p[0]-q[0]) <= 10 and abs(p[1]-q[1]) <= 10
        chain = [segs.pop(0)]
        while segs:
            end = chain[-1][1]
            for i, (a, b) in enumerate(segs):
                if near(a, end):
                    chain.append((end, b)); segs.pop(i); break
                if near(b, end):
                    chain.append((end, a)); segs.pop(i); break
            else:
                raise SystemExit(f"  profile not a single closed contour in {gbr.name}")
        if not near(chain[-1][1], chain[0][0]):
            raise SystemExit(f"  profile loop does not close in {gbr.name}")
        chain[-1] = (chain[-1][0], chain[0][0])  # snap closure exactly
        out = head + [f"X{chain[0][0][0]}Y{chain[0][0][1]}D02*"]
        out += [f"X{b[0]}Y{b[1]}D01*" for a, b in chain]
        gbr.write_text("\n".join(out + tail) + "\n")
        print(f"    reordered profile into 1 closed loop ({len(chain)} segments) in {gbr.name}")


def export_drill(proj: dict, gerber_dir: Path) -> Path:
    pcb = proj["dir"] / proj["pcb"]
    run([
        "kicad-cli", "pcb", "export", "drill",
        "--output", str(gerber_dir) + "/",
        "--format", "excellon",
        "--excellon-separate-th",
        "--drill-origin", "plot",
        "--excellon-units", "mm",
        "--generate-map",
        "--map-format", "gerberx2",
        str(pcb),
    ])
    return gerber_dir


def zip_fab(proj: dict, ts: str) -> Path:
    fab_dir = proj["dir"] / "fab_output"
    out = fab_dir / f"{proj['name']}-fab-{ts}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(fab_dir.rglob("*")):
            if f.is_file() and f.suffix != ".zip":
                zf.write(f, f.relative_to(fab_dir))
    return out


def main() -> None:
    if not shutil.which("kicad-cli"):
        sys.exit("kicad-cli not found in PATH (install KiCad >= 8.0)")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    for proj in PROJECTS:
        print(f"\n=== {proj['name']} ===")
        if not (proj["dir"] / proj["pcb"]).exists():
            print(f"  skipping — {proj['pcb']} not found")
            continue

        assert_filled(proj)

        bom = export_bom(proj)
        pos = export_pos(proj)
        filter_pos(pos)
        gerbers = export_gerbers(proj)
        export_drill(proj, gerbers)
        linearize_profile(gerbers)  # after drill: the drill map gerber has arcs too
        reorder_profile(gerbers)
        archive = zip_fab(proj, ts)

        print(f"  BOM:      {bom.relative_to(CHARGE)}")
        print(f"  POS:      {pos.relative_to(CHARGE)}")
        print(f"  Gerbers:  {gerbers.relative_to(CHARGE)}/")
        print(f"  Archive:  {archive.relative_to(CHARGE)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
