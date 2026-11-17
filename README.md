# kicad_projects

My PCB designs in KiCad 10.

## USB charger boards (`USB/charge/`)

Two 4-layer boards that take **12–24 V DC in** and give **5 V USB charging out**,
using a TI **LMR33630ADDA** buck regulator.

| Board | Folder | Output |
|---|---|---|
| USB-A charger | [`USB/charge/USB-A/`](USB/charge/USB-A/) | 5 V, USB-A port (BC1.2 dedicated charging port) |
| USB-C charger | [`USB/charge/USB_C/`](USB/charge/USB_C/) | 5 V, USB-C port (Rp advertisement + BC1.2) |

**Protection chain:** PPTC fuse → Bourns thermal cutoff → reverse-polarity Schottky →
input TVS, plus a TVS on the 5 V rail and USBLC6 ESD protection on D+/D−.

- Design review notes and open items: [`USB/charge/README.md`](USB/charge/README.md)
- Thermal cutoff selection: [`USB/charge/USB-A/TCO_README.md`](USB/charge/USB-A/TCO_README.md)

## Tools

| Script | What it does |
|---|---|
| `USB/charge/tools/fab-export.py` | Exports BOM, pick-and-place, Gerbers and drill files into `fab_output/` |
| `USB/tools/kicad-strip-fills.py` | Git filter that strips zone fills from `.kicad_pcb` files |
| `USB/tools/setup-git-filters.sh` | Turns that filter on for your clone |

## Opening the boards

1. Install [KiCad 10](https://www.kicad.org/).
2. Open `USB_A.kicad_pro` or `USB_C.kicad_pro`.
3. In the PCB editor, press **B** (Fill All Zones) before exporting anything.
