#!/usr/bin/env python3
"""
Build daily NSE market cap CSVs from extracted PR archives.

Inputs:
  - bhav/isin_data/isin_master.csv         (NSE_SYMBOL -> ISIN map)
  - bhav/mcap_data/input_files/extracted/PRddmmyy/mcapDDMMYYYY.csv (one per trade date)

Output:
  - bhav/mcap_data/output/mcap_YYYY-MM-DD.csv  (one per trade date)
       columns: isin, source, trade_date, face_value, issue_size, market_cap
  - bhav/mcap_data/output/unmatched.csv        (NSE symbols not found in isin_master)
       columns: trade_date, symbol, security_name

Filters: only Series == 'EQ'.
"""
import csv
import glob
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BHAV_ROOT = os.path.dirname(SCRIPT_DIR)
ISIN_MASTER = os.path.join(BHAV_ROOT, 'isin_data', 'isin_master.csv')
EXTRACTED_DIR = os.path.join(SCRIPT_DIR, 'input_files', 'extracted')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
UNMATCHED_FILE = os.path.join(OUTPUT_DIR, 'unmatched.csv')

SOURCE = 'NSE'
OUTPUT_HEADER = ['_id', 'isin', 'source', 'trade_date', 'face_value', 'issue_size', 'market_cap']


def load_nse_isin_lookup(path):
    lookup = {}
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            sym = (row.get('NSE_SYMBOL') or '').strip().upper()
            isin = (row.get('_id') or '').strip()
            if sym and isin:
                lookup[sym] = isin
    print(f"Loaded {len(lookup)} NSE_SYMBOL -> ISIN mappings")
    return lookup


def parse_float(val):
    try:
        return float(str(val).strip().replace(',', ''))
    except (ValueError, TypeError, AttributeError):
        return None


def parse_int(val):
    try:
        return int(str(val).strip().replace(',', ''))
    except (ValueError, TypeError, AttributeError):
        return None


def parse_trade_date(val):
    """e.g. '12 JUN 2026' -> '2026-06-12'."""
    s = (val or '').strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, '%d %b %Y').strftime('%Y-%m-%d')
    except ValueError:
        return None


def find_mcap_file(extract_dir):
    """Return the mcap*.csv inside an extracted PR folder, or None."""
    candidates = []
    for entry in os.listdir(extract_dir):
        if entry.lower().startswith('mcap') and entry.lower().endswith('.csv'):
            candidates.append(os.path.join(extract_dir, entry))
    if not candidates:
        return None
    # If multiple, pick the first deterministically.
    return sorted(candidates)[0]


def normalize_keys(row):
    """Strip whitespace from keys + values to handle the padded PR csv columns."""
    return {(k or '').strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}


def process_mcap_file(path, isin_lookup, unmatched_writer):
    rows_out = []
    trade_date_iso = None
    matched = 0
    skipped_non_eq = 0
    skipped_no_isin = 0
    skipped_bad = 0

    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = normalize_keys(raw)

            series = (row.get('Series') or '').upper()
            if series != 'EQ':
                skipped_non_eq += 1
                continue

            td = parse_trade_date(row.get('Trade Date'))
            if not td:
                skipped_bad += 1
                continue
            trade_date_iso = trade_date_iso or td

            symbol = (row.get('Symbol') or '').upper()
            isin = isin_lookup.get(symbol)
            if not isin:
                skipped_no_isin += 1
                unmatched_writer.writerow([td, symbol, row.get('Security Name', '')])
                continue

            face_value = parse_float(row.get('Face Value(Rs.)'))
            issue_size = parse_int(row.get('Issue Size'))
            market_cap = parse_float(row.get('Market Cap(Rs.)'))

            doc_id = f"{isin}_{td}"
            rows_out.append([doc_id, isin, SOURCE, td, face_value, issue_size, market_cap])
            matched += 1

    return trade_date_iso, rows_out, {
        'matched': matched,
        'non_eq': skipped_non_eq,
        'no_isin': skipped_no_isin,
        'bad': skipped_bad,
    }


def main():
    if not os.path.exists(ISIN_MASTER):
        print(f"ERROR: isin master not found at {ISIN_MASTER}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(EXTRACTED_DIR):
        print(f"ERROR: extracted dir not found at {EXTRACTED_DIR}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    isin_lookup = load_nse_isin_lookup(ISIN_MASTER)

    pr_dirs = sorted(
        d for d in glob.glob(os.path.join(EXTRACTED_DIR, 'PR*'))
        if os.path.isdir(d)
    )
    if not pr_dirs:
        print(f"No extracted PR* folders under {EXTRACTED_DIR}")
        return

    print(f"Found {len(pr_dirs)} extracted PR folders")

    with open(UNMATCHED_FILE, 'w', newline='') as uf:
        unmatched_writer = csv.writer(uf)
        unmatched_writer.writerow(['trade_date', 'symbol', 'security_name'])

        total_files = 0
        total_rows = 0
        skipped_files = 0

        for d in pr_dirs:
            mcap_path = find_mcap_file(d)
            if not mcap_path:
                skipped_files += 1
                print(f"SKIP (no mcap*.csv): {d}")
                continue

            try:
                trade_date_iso, rows, stats = process_mcap_file(
                    mcap_path, isin_lookup, unmatched_writer
                )
            except Exception as e:
                skipped_files += 1
                print(f"SKIP (error: {e}): {mcap_path}")
                continue

            if not rows or not trade_date_iso:
                skipped_files += 1
                print(f"SKIP (no EQ rows): {mcap_path}")
                continue

            out_path = os.path.join(OUTPUT_DIR, f"mcap_{trade_date_iso}.csv")
            with open(out_path, 'w', newline='') as of:
                w = csv.writer(of)
                w.writerow(OUTPUT_HEADER)
                w.writerows(rows)

            total_files += 1
            total_rows += len(rows)
            print(
                f"OK {os.path.basename(mcap_path)} -> {os.path.basename(out_path)} "
                f"matched={stats['matched']} non_eq={stats['non_eq']} "
                f"no_isin={stats['no_isin']} bad={stats['bad']}"
            )

    print(f"\nDone. files_written={total_files} rows_written={total_rows} skipped_files={skipped_files}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"Unmatched log: {UNMATCHED_FILE}")


if __name__ == '__main__':
    main()
