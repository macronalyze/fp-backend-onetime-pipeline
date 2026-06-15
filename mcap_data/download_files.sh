#!/usr/bin/env bash
# Download NSE PR (Price + Market Cap) zip files for a date range and extract them.
#
# Usage:
#   ./download_files.sh DDMMYYYY DDMMYYYY
#   e.g. ./download_files.sh 01062026 12062026
#
# Scope:
#   1. Download all PRddmmyy.zip files in the given range -> input_files/zips/
#   2. Extract each zip                                   -> input_files/extracted/<PRddmmyy>/
#   Failures are logged to download.log and ignored.

set -u

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 START_DATE END_DATE   (DDMMYYYY DDMMYYYY)" >&2
    exit 1
fi

START="$1"
END="$2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP_DIR="$SCRIPT_DIR/input_files/zips"
EXTRACT_DIR="$SCRIPT_DIR/input_files/extracted"
LOG_FILE="$SCRIPT_DIR/download.log"

mkdir -p "$ZIP_DIR" "$EXTRACT_DIR"
: > "$LOG_FILE"

BASE_URL="https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
REFERER="https://www.nseindia.com/"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Validate dates parse on macOS BSD `date`
if ! date -j -f "%d%m%Y" "$START" +%s >/dev/null 2>&1; then
    echo "Invalid START date: $START (expected DDMMYYYY)" >&2
    exit 1
fi
if ! date -j -f "%d%m%Y" "$END" +%s >/dev/null 2>&1; then
    echo "Invalid END date: $END (expected DDMMYYYY)" >&2
    exit 1
fi

START_EPOCH=$(date -j -f "%d%m%Y" "$START" +%s)
END_EPOCH=$(date -j -f "%d%m%Y" "$END" +%s)

if [[ "$START_EPOCH" -gt "$END_EPOCH" ]]; then
    echo "START_DATE must be <= END_DATE" >&2
    exit 1
fi

log "Downloading PR zips from $START to $END"

cur="$START"
total=0
ok=0
fail=0
skipped_weekend=0
skipped_existing=0

while :; do
    # Day of week: 1=Mon ... 7=Sun
    dow=$(date -j -f "%d%m%Y" "$cur" "+%u")

    if [[ "$dow" == "6" || "$dow" == "7" ]]; then
        skipped_weekend=$((skipped_weekend + 1))
    else
        ddmmyy=$(date -j -f "%d%m%Y" "$cur" "+%d%m%y")
        fname="PR${ddmmyy}.zip"
        url="${BASE_URL}/${fname}"
        out="${ZIP_DIR}/${fname}"
        total=$((total + 1))

        if [[ -s "$out" ]]; then
            skipped_existing=$((skipped_existing + 1))
            log "SKIP (exists): $fname"
        else
            # -f: fail on HTTP errors, -s: silent, -L: follow redirects
            if curl -fsSL \
                -A "$UA" \
                -H "Referer: $REFERER" \
                -H "Accept: */*" \
                --max-time 60 \
                -o "$out" \
                "$url"; then
                ok=$((ok + 1))
                log "OK: $fname"
            else
                rc=$?
                fail=$((fail + 1))
                rm -f "$out"
                log "FAIL ($rc): $fname  $url"
            fi
            sleep 0.2
        fi
    fi

    if [[ "$cur" == "$END" ]]; then
        break
    fi
    cur=$(date -j -v+1d -f "%d%m%Y" "$cur" "+%d%m%Y")
done

log "Download summary: attempted=$total ok=$ok fail=$fail skipped_existing=$skipped_existing skipped_weekend=$skipped_weekend"

# ---------- Extraction ----------
log "Extracting zips from $ZIP_DIR -> $EXTRACT_DIR"

ext_ok=0
ext_fail=0
ext_skip=0

shopt -s nullglob
for zip in "$ZIP_DIR"/*.zip; do
    base=$(basename "$zip" .zip)
    target="$EXTRACT_DIR/$base"

    if [[ -d "$target" ]] && [[ -n "$(ls -A "$target" 2>/dev/null)" ]]; then
        ext_skip=$((ext_skip + 1))
        continue
    fi

    mkdir -p "$target"
    # Extract only the mcap*.csv file (case-insensitive). -j flattens paths.
    if unzip -o -j -C -q "$zip" "mcap*.csv" -d "$target" >/dev/null 2>&1; then
        if compgen -G "$target"/[mM][cC][aA][pP]*.csv > /dev/null; then
            ext_ok=$((ext_ok + 1))
        else
            ext_fail=$((ext_fail + 1))
            log "EXTRACT FAIL (no mcap file inside): $zip"
            rmdir "$target" 2>/dev/null || true
        fi
    else
        ext_fail=$((ext_fail + 1))
        log "EXTRACT FAIL: $zip"
        rmdir "$target" 2>/dev/null || true
    fi
done

log "Extract summary: ok=$ext_ok fail=$ext_fail skipped=$ext_skip"
log "Done."
