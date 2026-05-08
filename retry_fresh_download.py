#!/usr/bin/env python3
"""
Find files < 1KB, re-fetch the download link from Samco for that exact date,
then download the file fresh.
"""
import csv, os, time, re, urllib.request, sys

INPUT_CSV = 'all_bhavcopy_links.csv'
BASE_DIR = 'raw_input_files'
NSE_DIR = os.path.join(BASE_DIR, 'nse')
BSE_DIR = os.path.join(BASE_DIR, 'bse')
MIN_SIZE = 1024 * 10  # 1 KB

SAMCO_URL = 'https://www.samco.in/bse_nse_mcx/getBhavcopy'

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Accept': 'text/html, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.samco.in',
    'Referer': 'https://www.samco.in/bhavcopy-nse-bse-mcx',
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}

DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.samco.in/bhavcopy-nse-bse-mcx',
}


def fetch_links_for_date(date_iso):
    """Call Samco API for a single date and return dict of {exchange: download_url}."""
    # date_iso is yyyy-mm-dd
    post_data = (
        f"start_date={date_iso}&end_date={date_iso}"
        f"&bhavcopy_data%5B%5D=NSE&bhavcopy_data%5B%5D=BSE&show_or_down=1"
    ).encode()

    req = urllib.request.Request(SAMCO_URL, data=post_data, headers=COMMON_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8', errors='replace')

    links = {}
    # Find all download links in the response
    for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]+)</a>', html):
        url, fname = m.group(1), m.group(2)
        if '_NSE' in fname:
            links['nse'] = url
        elif '_BSE' in fname:
            links['bse'] = url
    return links


def download_file(url, out_file):
    """Download a file and return bytes written."""
    req = urllib.request.Request(url, headers=DOWNLOAD_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    if len(data) >= MIN_SIZE:
        with open(out_file, 'wb') as fout:
            fout.write(data)
        return len(data)
    return 0


# --- Main ---
with open(INPUT_CSV) as f:
    rows = list(csv.DictReader(f))

# Find files < 1KB and group by date
retry_dates = {}  # date_iso -> [(exchange, out_file), ...]
for row in rows:
    date_str = row['date']          # dd-mm-yyyy
    file_name = row['file_name']

    exchange = 'nse' if '_NSE' in file_name else 'bse'
    dest_dir = NSE_DIR if exchange == 'nse' else BSE_DIR

    parts = date_str.split('-')
    date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
    out_file = os.path.join(dest_dir, f"{exchange}-{date_iso}.csv")

    if not os.path.exists(out_file) or os.path.getsize(out_file) < MIN_SIZE:
        retry_dates.setdefault(date_iso, []).append((exchange, out_file))

if not retry_dates:
    print("No files under 1KB found. All good!")
    sys.exit(0)

print(f"Found {sum(len(v) for v in retry_dates.values())} files under 1KB across {len(retry_dates)} dates.")
print()

success = 0
still_empty = 0

for i, (date_iso, items) in enumerate(sorted(retry_dates.items()), 1):
    print(f"[{i}/{len(retry_dates)}] Fetching links for {date_iso}...")
    try:
        links = fetch_links_for_date(date_iso)
    except Exception as e:
        print(f"  -> FAIL fetching links: {e}", file=sys.stderr)
        continue

    for exchange, out_file in items:
        if exchange not in links:
            print(f"  -> No {exchange.upper()} link found for {date_iso}")
            still_empty += 1
            continue

        try:
            nbytes = download_file(links[exchange], out_file)
            if nbytes:
                print(f"  -> OK {exchange.upper()}: {nbytes} bytes -> {out_file}")
                success += 1
            else:
                print(f"  -> Still empty for {exchange.upper()}")
                still_empty += 1
        except Exception as e:
            print(f"  -> FAIL downloading {exchange.upper()}: {e}", file=sys.stderr)
            still_empty += 1

    time.sleep(0.5)

print(f"\nDone. Recovered: {success}, Still empty: {still_empty}")
