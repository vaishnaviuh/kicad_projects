#!/usr/bin/env bash
set -e
git config filter.kicadfills.clean "python3 $(git rev-parse --show-toplevel)/USB/tools/kicad-strip-fills.py"
git config filter.kicadfills.smudge "cat"
echo "kicadfills filter configured."
