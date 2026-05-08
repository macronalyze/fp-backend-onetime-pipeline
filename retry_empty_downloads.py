#!/usr/bin/env python3
import csv, os, time, urllib.request, sys

INPUT_CSV = 'all_bhavcopy_links.csv'
BASE_DIR = 'raw_input_files'
NSE_DIR = os.path.join(BASE_DIR, 'nse')
BSE_DIR = os.path.join(BASE_DIR, 'bse')
MIN_SIZE = 1024  # 1 KB

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.samco.in/bhavcopy-nse-bse-mcx',
}

with open(INPUT_CSV) as f:
    rows = list(csv.DictReader(f))

# Find files that are < 1KB
retry_list = []
for row in rows:
    date_str = row['date']
    file_name = row['file_name']
    url = row['download_link']

    exchange = 'nse' if '_NSE' in file_name else 'bse'
    dest_dir = NSE_DIR if exchange == 'nse' else BSE_DIR

    parts = date_str.split('-')
    date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
    out_file = os.path.join(dest_dir, f"{exchange}-{date_iso}.csv")

    if not os.path.exists(out_file) or os.path.getsize(out_file) < MIN_SIZE:
        retry_list.append((out_file, url))

if not retry_list:
    print("No files under 1KB found. All good!")
    sys.exit(0)

print(f"Found {len(retry_list)} files under 1KB. Re-downloading...")
for i, (out_file, url) in enumerate(retry_list, 1):
    print(f"[{i}/{len(retry_list)}] Retrying: {out_file}")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < MIN_SIZE:
            print(f"  -> Still empty/small ({len(data)} bytes), skipping write")
        else:
            with open(out_file, 'wb') as fout:
                fout.write(data)
            print(f"  -> OK ({len(data)} bytes)")
    except Exception as e:
        print(f"  -> FAIL: {e}", file=sys.stderr)

    if i < len(retry_list):
        time.sleep(0.2)

print("Done.")
