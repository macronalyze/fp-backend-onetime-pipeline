#!/usr/bin/env python3
"""
Ingest NSE and BSE bhavcopy CSV files into MongoDB.
Collection: bhav.raw_bhav_data_v3 (zstd compressed, monthly buckets, 5 years)

Document structure:
  _id: "{isin}_{yyyy-mm}"
  i:  isin
  d:  [ { dt, ex, sym, o, h, l, c, la, pc, tq, tv, tt, [sr], [sc], [sg] }, ... ]

Optimizations vs v2:
- Monthly bucketed documents (~17x fewer docs)
- Massive index savings (fewer _id entries)
- No separate query index needed (_id prefix = ISIN lookup)
- Only data from START_YEAR onwards
"""
import csv, os, glob, sys
from datetime import datetime
from pymongo import MongoClient, UpdateOne

MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'bhav'
COLLECTION = 'raw_bhav_data_v3'
BATCH_SIZE = 5000
START_YEAR = 2021  # Only ingest data from this year onwards

NSE_DIR = 'raw_input_files/nse'
BSE_DIR = 'raw_input_files/bse'
ISIN_MASTER = 'isin_data/isin_master.csv'


def load_bse_isin_lookup():
    lookup = {}
    with open(ISIN_MASTER) as f:
        for row in csv.DictReader(f):
            bse_code = row['BSE_CODE'].strip()
            isin = row['_id'].strip()
            if bse_code and isin:
                lookup[bse_code] = isin
    print(f"Loaded {len(lookup)} BSE code -> ISIN mappings")
    return lookup


def parse_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def process_nse_file(filepath):
    basename = os.path.basename(filepath)
    date_str = basename[4:14]
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    if date_obj.year < START_YEAR:
        return

    month_key = date_str[:7]  # yyyy-mm

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            isin = row.get('ISIN', '').strip()
            if not isin:
                continue

            entry = {
                'dt': date_obj,
                'ex': 'nse',
                'sym': row.get('SYMBOL', '').strip(),
                'o': parse_float(row.get('OPEN')),
                'h': parse_float(row.get('HIGH')),
                'l': parse_float(row.get('LOW')),
                'c': parse_float(row.get('CLOSE')),
                'la': parse_float(row.get('LAST')),
                'pc': parse_float(row.get('PREVCLOSE')),
                'tq': parse_int(row.get('TOTTRDQTY')),
                'tv': parse_float(row.get('TOTTRDVAL')),
                'tt': parse_int(row.get('TOTALTRADES')),
            }
            series = row.get('SERIES', '').strip()
            if series:
                entry['sr'] = series

            doc_id = f"{isin}_{month_key}"
            yield UpdateOne(
                {'_id': doc_id},
                {
                    '$setOnInsert': {'i': isin},
                    '$push': {'d': entry}
                },
                upsert=True
            )


def process_bse_file(filepath, bse_isin_lookup):
    basename = os.path.basename(filepath)
    date_str = basename[4:14]
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    if date_obj.year < START_YEAR:
        return

    month_key = date_str[:7]

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sc_code = row.get('SC_CODE', '').strip()
            isin = bse_isin_lookup.get(sc_code, '')
            if not isin:
                continue

            entry = {
                'dt': date_obj,
                'ex': 'bse',
                'sym': row.get('SC_NAME', '').strip(),
                'o': parse_float(row.get('OPEN')),
                'h': parse_float(row.get('HIGH')),
                'l': parse_float(row.get('LOW')),
                'c': parse_float(row.get('CLOSE')),
                'la': parse_float(row.get('LAST')),
                'pc': parse_float(row.get('PREVCLOSE')),
                'tq': parse_int(row.get('NO_OF_SHRS')),
                'tv': parse_float(row.get('NET_TURNOV')),
                'tt': parse_int(row.get('NO_TRADES')),
            }
            if sc_code:
                entry['sc'] = sc_code
            sc_group = row.get('SC_GROUP', '').strip()
            if sc_group:
                entry['sg'] = sc_group

            doc_id = f"{isin}_{month_key}"
            yield UpdateOne(
                {'_id': doc_id},
                {
                    '$setOnInsert': {'i': isin},
                    '$push': {'d': entry}
                },
                upsert=True
            )


def flush_batch(collection, batch):
    if batch:
        result = collection.bulk_write(batch, ordered=False)
        return result.upserted_count + result.modified_count
    return 0


def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    coll = db[COLLECTION]

    bse_isin_lookup = load_bse_isin_lookup()

    # --- Process NSE files ---
    nse_files = sorted(glob.glob(os.path.join(NSE_DIR, 'nse-*.csv')))
    print(f"\nProcessing {len(nse_files)} NSE files (from {START_YEAR} onwards)...")
    batch = []
    total_nse = 0
    skipped_empty = 0
    skipped_old = 0

    for i, fpath in enumerate(nse_files, 1):
        if os.path.getsize(fpath) < 1024:
            skipped_empty += 1
            continue
        count_before = len(batch)
        for op in process_nse_file(fpath):
            batch.append(op)
            if len(batch) >= BATCH_SIZE:
                total_nse += flush_batch(coll, batch)
                batch = []
        if len(batch) == count_before and skipped_empty == 0:
            skipped_old += 1
        if i % 500 == 0:
            print(f"  NSE: {i}/{len(nse_files)} files processed...")

    total_nse += flush_batch(coll, batch)
    batch = []
    print(f"  NSE done: {total_nse} ops, {skipped_empty} empty, {skipped_old} pre-{START_YEAR} skipped")

    # --- Process BSE files ---
    bse_files = sorted(glob.glob(os.path.join(BSE_DIR, 'bse-*.csv')))
    print(f"\nProcessing {len(bse_files)} BSE files (from {START_YEAR} onwards)...")
    total_bse = 0
    skipped_empty = 0
    skipped_old = 0

    for i, fpath in enumerate(bse_files, 1):
        if os.path.getsize(fpath) < 1024:
            skipped_empty += 1
            continue
        count_before = len(batch)
        for op in process_bse_file(fpath, bse_isin_lookup):
            batch.append(op)
            if len(batch) >= BATCH_SIZE:
                total_bse += flush_batch(coll, batch)
                batch = []
        if len(batch) == count_before and skipped_empty == 0:
            skipped_old += 1
        if i % 500 == 0:
            print(f"  BSE: {i}/{len(bse_files)} files processed...")

    total_bse += flush_batch(coll, batch)
    print(f"  BSE done: {total_bse} ops, {skipped_empty} empty, {skipped_old} pre-{START_YEAR} skipped")

    print(f"\nTotal documents in collection: {coll.estimated_document_count()}")
    client.close()


if __name__ == '__main__':
    main()
