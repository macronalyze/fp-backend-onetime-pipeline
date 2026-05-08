#!/usr/bin/env python3
"""
Merge NSE and BSE ISIN master files into a single lookup table.
Output: isin_data/isin_master.csv
"""
import csv

NSE_FILE = 'isin_data/nse_isin_data.csv'
BSE_FILE = 'isin_data/bse_isin_data.csv'
OUTPUT = 'isin_data/isin_master.csv'

# Load NSE data keyed by ISIN
nse_by_isin = {}
with open(NSE_FILE) as f:
    reader = csv.DictReader(f)
    for row in reader:
        isin = row.get(' ISIN NUMBER', '').strip()
        symbol = row.get('SYMBOL', '').strip()
        name = row.get('NAME OF COMPANY', '').strip()
        series = row.get(' SERIES', '').strip()
        if isin and series == 'EQ':
            nse_by_isin[isin] = {'symbol': symbol, 'name': name}

# Load BSE data keyed by ISIN
bse_by_isin = {}
with open(BSE_FILE) as f:
    reader = csv.DictReader(f)
    for row in reader:
        isin = row.get('ISIN No', '').strip()
        sc_code = row.get('Security Code', '').strip()
        name = row.get('Issuer Name', '').strip()
        status = row.get('Status', '').strip()
        instrument = row.get('Instrument', '').strip()
        if isin and status == 'Active' and instrument == 'Equity':
            bse_by_isin[isin] = {'sc_code': sc_code, 'name': name}

# Merge on ISIN
all_isins = sorted(set(nse_by_isin.keys()) | set(bse_by_isin.keys()))

with open(OUTPUT, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['_id', 'COMPANY_NAME', 'NSE_SYMBOL', 'BSE_CODE'])

    both = 0
    nse_only = 0
    bse_only = 0

    for isin in all_isins:
        nse = nse_by_isin.get(isin)
        bse = bse_by_isin.get(isin)

        name = (nse['name'] if nse else bse['name'])
        nse_symbol = nse['symbol'] if nse else ''
        bse_code = bse['sc_code'] if bse else ''

        # only include if the ISIN starts with INE (Indian securities - Equity or Debt alone)
        if isin.startswith('INE'):
            writer.writerow([isin, name, nse_symbol, bse_code])
        else:
            print(f"Skipping non-IN ISIN: {isin} ({name}) {nse_symbol} {bse_code}")

        if nse and bse:
            both += 1
        elif nse:
            nse_only += 1
        else:
            bse_only += 1

print(f"Output: {OUTPUT}")
print(f"Total ISINs: {len(all_isins)}")
print(f"  Both exchanges: {both}")
print(f"  NSE only: {nse_only}")
print(f"  BSE only: {bse_only}")
