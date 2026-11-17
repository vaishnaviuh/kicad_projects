#!/usr/bin/env python3
"""Git clean filter for KiCad .kicad_pcb files.

Removes every computed `(filled_polygon ...)` block from a board file read on
stdin and writes the result to stdout. These blocks are derived data: KiCad
regenerates them on "Fill All Zones" and reorders the coordinates each time,
producing huge, meaningless diffs. Stripping them on `git add` keeps commits to
real design changes (footprints, tracks, zone outlines, nets).

Zone *settings* such as `(fill yes ...)` are left untouched -- only the
`(filled_polygon ...)` results are removed. After checkout you must run
"Fill All Zones" (hotkey B) before exporting Gerbers/fabrication output.

Registered as the `kicadfills` clean filter via .gitattributes; see
tools/setup-git-filters.sh to enable it in a fresh clone.
"""
import sys

KEY = "(filled_polygon"


def strip(text: str) -> str:
    out = []
    i = 0
    while True:
        j = text.find(KEY, i)
        if j < 0:
            out.append(text[i:])
            break
        line_start = text.rfind("\n", 0, j) + 1  # keep everything before this line
        out.append(text[i:line_start])
        depth = 0
        k = j
        while k < len(text):
            c = text[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        end = k + 1
        if end < len(text) and text[end] == "\n":
            end += 1  # drop the block's trailing newline too
        i = end
    return "".join(out)


if __name__ == "__main__":
    sys.stdout.write(strip(sys.stdin.read()))
