#!/usr/bin/env python3
import csv, os, time, random, urllib.request, sys

INPUT_CSV = 'all_bhavcopy_links.csv'
BASE_DIR = 'raw_input_files'
NSE_DIR = os.path.join(BASE_DIR, 'nse')
BSE_DIR = os.path.join(BASE_DIR, 'bse')

os.makedirs(NSE_DIR, exist_ok=True)
os.makedirs(BSE_DIR, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.samco.in/bhavcopy-nse-bse-mcx',
}

with open(INPUT_CSV) as f:
    rows = list(csv.DictReader(f))

total = len(rows)
print(f"Total files to download: {total}")

for i, row in enumerate(rows, 1):
    date_str = row['date']          # dd-mm-yyyy
    file_name = row['file_name']    # 20160101_NSE.csv
    url = row['download_link']

    # Determine exchange
    exchange = 'nse' if '_NSE' in file_name else 'bse'
    dest_dir = NSE_DIR if exchange == 'nse' else BSE_DIR

    # Convert dd-mm-yyyy -> yyyy-mm-dd
    parts = date_str.split('-')
    date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"

    out_file = os.path.join(dest_dir, f"{exchange}-{date_iso}.csv")

    if os.path.exists(out_file):
        print(f"[{i}/{total}] SKIP (exists): {out_file}")
        continue

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(out_file, 'wb') as fout:
            fout.write(data)
        print(f"[{i}/{total}] OK: {out_file}")
    except Exception as e:
        print(f"[{i}/{total}] FAIL: {out_file} -> {e}", file=sys.stderr)

    # Small delay between downloads
    if i < total:
        time.sleep(0.05)

print("Done.")
