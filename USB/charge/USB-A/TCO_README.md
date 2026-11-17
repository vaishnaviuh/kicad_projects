# TCO1 — Bourns SA Series Thermal Cutoff

## What it is
Bimetal thermal breaker. Non-polarized (pin 1 = pin 2, no orientation).
2 electrical terminals, each brought out as 2 physical pads (4 pads total) —
matches your custom `Bourns_TCO.kicad_mod`.

## Part options
| Part | Trip Temp | Reset |
|---|---|---|
| SA72SB0 | 72°C ±5°C | auto below (trip−10°C) |
| **SA77SB0** | **77°C ±5°C** ← **current best-guess selection (UNVERIFIED)** | ″ |
| SA82SB0 | 82°C ±5°C | ″ |
| SA85SB0 | 85°C ±5°C | ″ |

**SA77SB0 is a placeholder, not a confirmed choice.** Based on rough thermal
estimate only (~3-3.5W board dissipation (3A target), sealed housing, ~35-45°C rise above
ambient, realistic 30-40°C field ambient → ~75-80°C worst case at TCO1's
location). All four variants are pin-compatible — swapping later changes
nothing else on the board. **Do not release to production on this value alone
— see verification procedure below.**

**Reset needs BOTH:** temp drops ≥10°C below min trip point, **and** power cycled off/on.
Not a silent auto-recovery — device stays off until unplugged/replugged even after cooling.

## Ratings (all far above our ~1.5A max input current design — current is not the limiting factor here)
- Contact: DC9V/25A, 6000 cycles
- Resistance: 7mΩ max
- App. temp range: −30 to 100°C

## Placement
Mount where board heat is highest (per Bourns' own design caution) → next to U1, in series in VIN path.

## Open action item — thermal validation (send to test/EMS partner)

**Objective:** measure steady-state board temperature at TCO1's mounting
location under worst-case real conditions, to confirm or correct the
SA77SB0 best-guess above.

**Equipment**
- DC power supply, adjustable, 12V and 24V
- Electronic load / resistive load bank: sink 3A at 5V (15W), continuous
- K-type thermocouple taped/soldered directly to the PCB pad at TCO1 —
  not an IR gun alone, it can't see inside the closed housing
- Data logger or multimeter with thermocouple input, logged over time
- The **fully assembled unit in its actual snap-fit housing** — bare-board
  numbers will read lower than reality and invalidate the test

**Conditions to run (worst case governs the final part selection)**
1. 12V input, 3A output load, still air, 25°C ambient
2. 24V input, 3A output load, still air, 25°C ambient
3. Repeat condition 2 at ~40°C ambient if the deployment environment isn't
   climate-controlled (adds real-world margin)

**Procedure**
1. Assemble fully in housing, thermocouple in place before closing it.
2. Apply input voltage and full 3A load at the USB-A output.
3. Log temperature at TCO1's location every 1-2 minutes.
4. Run until steady state: **<1°C change over 10 consecutive minutes**
   (typically 30-60 min in a sealed enclosure — don't stop early).
5. Record the final steady-state temperature for each condition tested.

**Selection rule**
Take the highest steady-state temperature recorded across all conditions.
Pick the trip variant such that:

    Trip temperature − measured steady-state temperature ≥ 15-20°C

Example: if worst-case measured is 58°C, SA77SB0 (19°C margin) is a good
choice. If it comes in at 65-70°C+, move to SA82SB0/SA85SB0 instead — and
treat that result as a signal the layout's thermal path may need attention,
not just a part swap.

**Deliverable expected back:** temperature-vs-time log for each condition,
final steady-state numbers, ambient conditions used, and photos confirming
thermocouple placement at TCO1's actual pad.

**Do not finalize the part choice before this measurement exists.**

## Handling notes
- Reflow only (no wave/flow soldering); peak 245-260°C, 5-10s
- Not washable, no ultrasonic cleaning after mounting
- Avoid moisture/direct sunlight/corrosive gas exposure
