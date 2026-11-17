# USB Charger Boards — Design Check & Fab Outputs

Two KiCad projects, both 12–24V DC in → 5V USB charging out:

| Project | Output | Regulator | Status of review |
|---|---|---|---|
| `USB-A/` | 5V / 2.1A, USB-A port (BC1.2 DCP) | TI LMR33630ADDA | **Reviewed — findings below** |
| `USB_C/` | 5V, USB-C port (Rp advertisement + BC1.2 DCP) | TI LMR33630ADDA | **Reviewed — findings below** |

## Goal

Go through each board thoroughly, one at a time, before production:
ERC/ERC-parity, DRC, schematic/netlist sanity, current paths and copper
sizing, protection chain, and fab-output freshness. USB-A first, then USB-C.

## Tooling notes (apply to both projects)

- **Zone fills are stripped from commits** by the `kicadfills` clean filter
  (`USB/tools/kicad-strip-fills.py`). The filter must be enabled per
  clone: run `USB/tools/setup-git-filters.sh` once, otherwise every
  KiCad save shows thousands of `filled_polygon` diff lines. (This was
  missing in this clone and has been enabled now.)
- A fresh checkout therefore has **empty pours** — run Fill All Zones (`B`)
  in pcbnew (or the headless equivalent) before exporting anything.
- **`tools/fab-export.py`** exports BOM, pick-and-place,
  4-layer Gerbers + Excellon drill, and a timestamped zip for **both**
  projects into `<project>/fab_output/`. It refuses to run on unfilled
  boards. These schematics have no MPN field, so the BOM groups by
  Value + Footprint.

## USB-A review findings (2026-07-29)

### Checks run

ERC, DRC with zone refill and schematic parity (KiCad 10.0.5 CLI), full
netlist trace, per-net copper measurement on the board file, gerber content
check against the current layout.

### Critical — fix before fabrication

1. **VBUS trace is far too thin for 2.1A.** The 5V path after the ferrite
   bead (FB1 pad 1 → J2 pin 1) runs ~19mm of **0.2mm-wide** track on F.Cu.
   At 2.1A that is roughly 45–50mΩ → ~100mV drop and substantial self-heating
   (IPC-2221 wants ~1mm+ at this current for a modest temperature rise).
   `VOUT_5V` before the bead has a dedicated In2.Cu plane — the problem is
   only the post-FB1 stretch. Widen to ≥1mm and/or pour a VBUS polygon.
2. **FB1 is an unspecified generic 0603 ferrite bead sitting in the full
   2.1A path.** Many 0603 beads are rated 1–2A with ~100mΩ DCR; combined
   with finding 1 the port voltage can fall below the USB minimum of 4.75V
   at full load. Specify a part rated ≥3A with low DCR (tens of mΩ), or
   move to a larger package.

### Should fix

3. **Input current path is all 0.2mm track**: J1 → F1 (4.4mm) → TCO1
   (9.9mm) → D3 (17.1mm) → `VIN_P` (~23mm). Carries up to ~1.1A at 12V
   input. Electrically marginal-OK, but the resistive heating sits right
   next to TCO1, whose trip point is the subject of the open thermal
   validation — widen these to keep the thermal test honest.
4. **DRC: 3 starved-thermal errors** (1 spoke instead of min 2) on GND pads
   of CH1, CI1 (input HF decoupling) and CV1 (VCC cap). Nudge parts or
   adjust the zone so the pads get proper relief — or solid connections,
   which are preferable for decoupling anyway.
5. **ERC: 3 "power input pin not driven" errors** (U1 VIN, J2 VBUS, one
   power symbol). Connectivity is real (verified in netlist); add
   `PWR_FLAG` symbols to silence them so real regressions stay visible.
6. **Test-point net-name parity warnings** (TP1/TP2): labels
   `Net-(F1-Pad2)` / `Net-(D3-A)` exist only on one pin each and mismatch
   the board's net names (`/…` prefix). Rename to meaningful labels (e.g.
   `VIN_FUSED`, `VIN_TCO`) and re-sync the PCB.

### Verified good

- **Regulation:** FB divider 100k/24.9k → 5.016V nominal (LMR33630 1.0V
  ref). EN divider 715k/100k → converter enables at ~10V input (UVLO
  sensible for a 12–24V spec).
- **Buck support parts** match the LMR33630 datasheet application:
  2×4.7µF + 220nF input, 4×22µF output, 100nF boot, 1µF VCC, 8.2µH
  Würth WE-PDF (ripple ~1.2A p-p worst case at 24V in — acceptable;
  confirm saturation current ≥ ~3A when locking the part number).
- **Protection chain:** PPTC fuse → Bourns thermal cutoff → series SS34
  reverse-polarity Schottky → SMAJ28A input TVS; SMAJ6.0A on the 5V rail;
  USBLC6-2SC6 ESD on D+/D−. Sound arrangement.
- **DCP identification:** D+/D− joined through 100Ω (R_DCP1) — valid BC1.2
  dedicated-charging-port signature.
- **Layout fundamentals:** 4-layer stack with GND on F/In1/B and a 5V plane
  on In2; U1 exposed pad has 8×0.3mm thermal vias; 0 unconnected items after
  zone refill; USB-A shield tied to GND.
- **Gerbers are current:** inner layers included, and the copper matches the
  post-"L1 swap" layout (verified pad coordinates inside the gerber).
  Regenerated fresh with `tools/fab-export.py` anyway.

### Pre-existing open items (documented in `USB-A/TCO_README.md`)

- TCO1 = SA77SB0 is a **placeholder**; thermal validation in the real
  enclosure is required before locking the trip temperature.
- Exact part numbers to confirm at procurement: F1 (PPTC — must be rated for
  the 24V input, many 1812 PPTCs are 16V parts), L1, FB1 (see finding 2),
  LED colour for D4.

## 3A retarget — changes applied (2026-07-29)

The output target was raised to **5V / 3A**. The following was applied
directly to both projects (schematics + boards, verified by ERC/DRC):

- **USB-C CC advertisement fixed for 3A:** D_CCREF1 (zener) and R_CCREF1
  deleted; RC1/RC2 (now "10k 1%") pull CC1/CC2 straight to VOUT_5V — the
  spec-table 10k@5V = 3A signature. Board tracks retargeted and bridged;
  DRC 0 unconnected, parity clean.
- **Setpoint raised:** RFB1 24.9k → 24.3k on both boards → ~5.12V at the
  regulator, extra IR-drop budget at 3A (still <5.25V worst case).
- **USB-C L1: 15µH → 8.2µH** (aligned with USB-A; lower DCR at 3A; lock a
  part with Isat ≥ 4.5A, Irms ≥ 3.5A).
- **BOM values updated on both boards:** F1 "3A PPTC 30V" (2920), D3 "SS54"
  (SMC), FB1 "FerriteBead 4A 20mR" (1206).
- **Copper widened where the existing placement allows** (DRC-verified):
  input chain J1→F1→TCO1→D3 now mostly 0.6–1.0mm on both boards; VOUT_5V
  runs 0.5–0.8mm (plus the In2 plane, which carries most of it).

### Left for manual layout (placement is too tight for scripted edits)

1. **F1 / D3 / FB1 footprint upgrades** (1812→2920, SMA→SMC, 0603→1206):
   the bigger bodies collide with TP1/TP2/J1/TCO1 (F1), REN1/U1/D1 (D3) and
   L1/CO1/CO2 (FB1). Schematics carry the new footprints, so DRC's
   schematic-parity check flags exactly these three per board as the to-do.
   Alternatives if space stays tight: D3 in SMB (B340LB) and FB1 in 0805
   (TDK MPZ2012-class, 6A) are electrically adequate.
2. **VBUS remains thin** — the corridor from FB1 to the connector maxes out
   at 0.25–0.4mm (USB-A) / mostly 0.2mm (USB-C) between existing pads,
   tracks, and the board edge. For 3A this needs a real reroute: move the
   run away from the CO2/CO3 pad row, or drop to B.Cu with a pair of ≥0.6mm
   vias, or dedicate a VBUS pour. **This is the single most important
   remaining item.**
3. Starved-thermal spokes (3 on USB-A, 9 on USB-C) — unchanged, still open.
4. USB-A data-line signature: DCP short only guarantees ~1.5A draw; if the
   port should source its full capability to phones/tablets, add an Apple
   2.4A divider or an auto-signature IC (TPS2513-class). Type-A cannot
   advertise 3A regardless.
5. TCO thermal validation must now run at **3A / 15W** load (see
   `USB-A/TCO_README.md`); expect the trip variant to move up (SA82/SA85).

## USB-C review findings (2026-07-29)

Same core design as USB-A (LMR33630ADDA buck, identical protection chain and
divider values, L1 = 15µH here), so the shared verdicts above apply. Checks
run: ERC, DRC with zone refill + schematic parity (0 parity issues,
0 unconnected), netlist trace, per-net copper measurement.

### Critical — fix before fabrication

1. **CC pull-up value is not a valid USB-C combination.** CC1/CC2 each pull
   up through 10k (RC1/RC2) to a zener-derived 3.3V rail (BZX584C-3V3 biased
   ~3mA via R_CCREF1 560Ω from the 5V rail). The spec's Rp values are
   56k/22k/10k to 5V, or 36k/12k/**4.7k** to 3.3V — 10k to 3.3V is not in
   the table. Nominal vRd at the sink ≈ 1.11V, only ~0.1V below the 1.23V
   threshold where sinks read a **3A** advertisement; with resistor, zener,
   and Rd tolerances a sink can legitimately conclude 3A and overload this
   ~2A supply. Fix: change RC1/RC2 to **12k** (clean 1.5A advertisement), or
   drop the zener rail entirely and use 22k straight to VOUT_5V. (Per-pin
   separate Rp resistors are correctly present.)
2. **Same VBUS thin-trace problem as USB-A:** ~29mm of 0.2mm track
   (24.5mm F.Cu + 4.9mm B.Cu) between FB1 and the connector's four VBUS
   pins, no VBUS pour. Widen/pour as on USB-A.
3. **Same FB1 unspecified 0603 ferrite bead** in the full-load path.

### Should fix

4. **Input path all 0.2mm** (J1→F1→TCO1→D3→VIN_P, ~53mm total) — same as
   USB-A finding 3.
5. **DRC: 9 starved-thermal errors**, mostly the USB-C connector's GND pads
   (A1, B1, B12, shield — across F/In1/B zones) plus U1 pad 1. Connector
   ground return and shield deserve solid/multi-spoke connections.
6. **ERC: 3 off-grid endpoint warnings** around D_CCREF1 (wire stubs of
   0.013/0.04mm). Connectivity is currently intact, but off-grid ends are
   how nets silently break on the next edit — tidy them.
7. Same PWR_FLAG ERC nits as USB-A.

### Verified good

- All four VBUS pins (A4/A9/B4/B9) and all GND pins (A1/A12/B1/B12 + shell)
  are connected; D+/D− tied across both rows with the 100Ω BC1.2 DCP short;
  SBU1/SBU2 correctly left open; USBLC6-2SC6 ESD on the data pair.
- L1 = 15µH (this board's "inductor swap"): ripple
  ~0.66A p-p worst case — comfortable.
- Same 4-layer stack (GND on F/In1/B, 5V plane on In2), 0 unconnected items
  after refill, schematic/board parity clean.
