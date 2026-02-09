#!/usr/bin/env bash
set -euo pipefail

CSV="${1:?Usage: $0 <file.csv>}"
BASE="/xnat-data/xnat/archive/RTDLHN/arc001"

# Archive folder in the same directory as this script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
OUTDIR="$SCRIPT_DIR/HeadNodeBatch13"
mkdir -p "$OUTDIR"

# Find the column index named "experiment" (case-insensitive)
exp_col="$(awk -F',' '
  NR==1 {
    for (i=1; i<=NF; i++) {
      h=$i; gsub(/\r/,"",h); gsub(/^[ \t"]+|[ \t"]+$/, "", h); h=tolower(h)
      if (h=="experiment") { print i; exit }
    }
    exit 1
  }' "$CSV")" || { echo "Error: CSV header must contain an \"experiment\" column."; exit 1; }

# Stream the experiment names and act on BASE/<experiment>
awk -F',' -v C="$exp_col" '
  NR>1 {
    v=$C
    gsub(/\r/,"",v)                           # strip CR
    gsub(/^[ \t"]+|[ \t"]+$/, "", v)          # trim
    if (v ~ /^".*"$/) { sub(/^"/,"",v); sub(/"$/,"",v) }
    if (length(v)) print v
  }' "$CSV" | while IFS= read -r exp; do
  path="$BASE/$exp"
  if [[ -d "$path" ]]; then
    echo "FOUND: $path"
    if [[ -e "$OUTDIR/$exp" ]]; then
      echo "SKIP (already exists): $OUTDIR/$exp"
    else
      cp -a -- "$path" "$OUTDIR/"
      echo "COPIED -> $OUTDIR/$exp"

      # === NEW: create a zip archive of the copied experiment ===
      echo "ZIPPING $exp ..."
      (cd "$OUTDIR" && zip -qr "${exp}.zip" "$exp")
      echo "ZIPPED -> $OUTDIR/${exp}.zip"

      # Optional: remove unzipped copy to save space
      # rm -rf "$OUTDIR/$exp"
    fi
  else
    echo "NOT FOUND: $path"
  fi
done

echo "Done. Archive at: $OUTDIR"