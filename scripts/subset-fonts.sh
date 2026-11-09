#!/usr/bin/env sh

# Regenerates fonts/*.woff2 from Sarasa-SuperTTC.ttc (Sarasa Gothic v1.0.42).
# Requires pyftsubset on PATH: pip install fonttools brotli
#
# The face number below is specific to that TTC: 220 is Sarasa Term J Regular.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TTC="${1:?usage: subset-fonts.sh path/to/Sarasa-SuperTTC.ttc}"

# Latin, Latin-1, common typographic punctuation, CJK punctuation and kana.
UNICODES="U+20-7E,U+A0-FF,U+2013,U+2014,U+2018,U+2019,U+201C,U+201D,U+2026,U+3000-30FF"

subset() {
  pyftsubset "$TTC" \
    --font-number="$1" \
    --unicodes="$UNICODES" \
    --flavor=woff2 \
    --layout-features='' \
    --no-hinting \
    --name-IDs=0,1,2 \
    --notdef-outline \
    --output-file="$ROOT/fonts/$2"
}

mkdir -p "$ROOT/fonts"
subset 220 sarasa-term-j-400.woff2
