#!/usr/bin/env python3
"""
Ingest NSE and BSE bhavcopy CSV files into MongoDB.
Collection: bhav.raw_bhav_data
_id format: {isin}_{yyyy-mm-dd}_{exchange}
"""
import csv, os, glob, sys
from datetime import datetime
from pymongo import MongoClient, UpdateOne

MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'bhav'
COLLECTION = 'raw_bhav_data'
BATCH_SIZE = 5000

NSE_DIR = 'raw_input_files/nse'
BSE_DIR = 'raw_input_files/bse'
ISIN_MASTER = 'isin_data/isin_master.csv'


def load_bse_isin_lookup():
    """Build BSE SC_CODE -> ISIN mapping from isin_master.csv."""
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
    """Parse an NSE CSV and yield documents."""
    # Extract date from filename: nse-yyyy-mm-dd.csv
    basename = os.path.basename(filepath)  # nse-2016-01-04.csv
    date_str = basename[4:14]              # 2016-01-04
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            isin = row.get('ISIN', '').strip()
            if not isin:
                continue

            doc_id = f"{isin}_{date_str}_nse"
            yield UpdateOne(
                {'_id': doc_id},
                {'$set': {
                    '_id': doc_id,
                    'isin': isin,
                    'date': date_obj,
                    'exchange': 'nse',
                    'symbol': row.get('SYMBOL', '').strip(),
                    'series': row.get('SERIES', '').strip(),
                    'sc_code': None,
                    'sc_group': None,
                    'open': parse_float(row.get('OPEN')),
                    'high': parse_float(row.get('HIGH')),
                    'low': parse_float(row.get('LOW')),
                    'close': parse_float(row.get('CLOSE')),
                    'last': parse_float(row.get('LAST')),
                    'prev_close': parse_float(row.get('PREVCLOSE')),
                    'total_traded_qty': parse_int(row.get('TOTTRDQTY')),
                    'total_traded_val': parse_float(row.get('TOTTRDVAL')),
                    'total_trades': parse_int(row.get('TOTALTRADES')),
                }},
                upsert=True
            )


def process_bse_file(filepath, bse_isin_lookup):
    """Parse a BSE CSV and yield documents."""
    basename = os.path.basename(filepath)  # bse-2016-01-04.csv
    date_str = basename[4:14]              # 2016-01-04
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sc_code = row.get('SC_CODE', '').strip()
            isin = bse_isin_lookup.get(sc_code, '')
            if not isin:
                continue

            doc_id = f"{isin}_{date_str}_bse"
            yield UpdateOne(
                {'_id': doc_id},
                {'$set': {
                    '_id': doc_id,
                    'isin': isin,
                    'date': date_obj,
                    'exchange': 'bse',
                    'symbol': row.get('SC_NAME', '').strip(),
                    'series': None,
                    'sc_code': sc_code,
                    'sc_group': row.get('SC_GROUP', '').strip(),
                    'open': parse_float(row.get('OPEN')),
                    'high': parse_float(row.get('HIGH')),
                    'low': parse_float(row.get('LOW')),
                    'close': parse_float(row.get('CLOSE')),
                    'last': parse_float(row.get('LAST')),
                    'prev_close': parse_float(row.get('PREVCLOSE')),
                    'total_traded_qty': parse_int(row.get('NO_OF_SHRS')),
                    'total_traded_val': parse_float(row.get('NET_TURNOV')),
                    'total_trades': parse_int(row.get('NO_TRADES')),
                }},
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
    print(f"\nProcessing {len(nse_files)} NSE files...")
    batch = []
    total_nse = 0
    skipped_empty = 0

    for i, fpath in enumerate(nse_files, 1):
        if os.path.getsize(fpath) < 1024:
            skipped_empty += 1
            continue
        for op in process_nse_file(fpath):
            batch.append(op)
            if len(batch) >= BATCH_SIZE:
                total_nse += flush_batch(coll, batch)
                batch = []
        if i % 500 == 0:
            print(f"  NSE: {i}/{len(nse_files)} files processed...")

    total_nse += flush_batch(coll, batch)
    batch = []
    print(f"  NSE done: {total_nse} docs upserted, {skipped_empty} empty files skipped")

    # --- Process BSE files ---
    bse_files = sorted(glob.glob(os.path.join(BSE_DIR, 'bse-*.csv')))
    print(f"\nProcessing {len(bse_files)} BSE files...")
    total_bse = 0
    skipped_empty = 0

    for i, fpath in enumerate(bse_files, 1):
        if os.path.getsize(fpath) < 1024:
            skipped_empty += 1
            continue
        for op in process_bse_file(fpath, bse_isin_lookup):
            batch.append(op)
            if len(batch) >= BATCH_SIZE:
                total_bse += flush_batch(coll, batch)
                batch = []
        if i % 500 == 0:
            print(f"  BSE: {i}/{len(bse_files)} files processed...")

    total_bse += flush_batch(coll, batch)
    print(f"  BSE done: {total_bse} docs upserted, {skipped_empty} empty files skipped")

    print(f"\nTotal documents in collection: {coll.estimated_document_count()}")
    client.close()


if __name__ == '__main__':
    main()
