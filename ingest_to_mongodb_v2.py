#!/usr/bin/env python3
"""
Ingest NSE and BSE bhavcopy CSV files into MongoDB.
Collection: bhav.raw_bhav_data_v2 (zstd compressed)

Optimizations vs v1:
- ObjectId _id (12 bytes vs ~30-byte string)
- Short field names
- Nullable fields omitted instead of stored as null
- Uses insert_many with ordered=False
"""
import csv, os, glob, sys
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'bhav'
COLLECTION = 'raw_bhav_data_v2'
BATCH_SIZE = 5000

NSE_DIR = 'raw_input_files/nse'
BSE_DIR = 'raw_input_files/bse'
ISIN_MASTER = 'isin_data/isin_master.csv'

# Field name mapping (for reference):
# i  = isin
# d  = date
# ex = exchange (nse/bse)
# sym = symbol
# sr = series (NSE only, omitted if empty)
# sc = sc_code (BSE only, omitted if empty)
# sg = sc_group (BSE only, omitted if empty)
# o  = open
# h  = high
# l  = low
# c  = close
# la = last
# pc = prev_close
# tq = total_traded_qty
# tv = total_traded_val
# tt = total_trades


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

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            isin = row.get('ISIN', '').strip()
            if not isin:
                continue

            doc = {
                'i': isin,
                'd': date_obj,
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
                doc['sr'] = series
            yield doc


def process_bse_file(filepath, bse_isin_lookup):
    basename = os.path.basename(filepath)
    date_str = basename[4:14]
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sc_code = row.get('SC_CODE', '').strip()
            isin = bse_isin_lookup.get(sc_code, '')
            if not isin:
                continue

            doc = {
                'i': isin,
                'd': date_obj,
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
                doc['sc'] = sc_code
            sc_group = row.get('SC_GROUP', '').strip()
            if sc_group:
                doc['sg'] = sc_group
            yield doc


def flush_batch(collection, batch):
    if not batch:
        return 0
    try:
        result = collection.insert_many(batch, ordered=False)
        return len(result.inserted_ids)
    except BulkWriteError as e:
        inserted = e.details.get('nInserted', 0)
        return inserted


def setup_indexes(coll):
    """Create the query index."""
    coll.create_index([('i', 1), ('d', -1)], name='i_1_d_-1')
    print("Index created: i_1_d_-1")


def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    coll = db[COLLECTION]

    setup_indexes(coll)
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
        for doc in process_nse_file(fpath):
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                total_nse += flush_batch(coll, batch)
                batch = []
        if i % 500 == 0:
            print(f"  NSE: {i}/{len(nse_files)} files processed...")

    total_nse += flush_batch(coll, batch)
    batch = []
    print(f"  NSE done: {total_nse} docs inserted, {skipped_empty} empty files skipped")

    # --- Process BSE files ---
    bse_files = sorted(glob.glob(os.path.join(BSE_DIR, 'bse-*.csv')))
    print(f"\nProcessing {len(bse_files)} BSE files...")
    total_bse = 0
    skipped_empty = 0

    for i, fpath in enumerate(bse_files, 1):
        if os.path.getsize(fpath) < 1024:
            skipped_empty += 1
            continue
        for doc in process_bse_file(fpath, bse_isin_lookup):
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                total_bse += flush_batch(coll, batch)
                batch = []
        if i % 500 == 0:
            print(f"  BSE: {i}/{len(bse_files)} files processed...")

    total_bse += flush_batch(coll, batch)
    print(f"  BSE done: {total_bse} docs inserted, {skipped_empty} empty files skipped")

    print(f"\nTotal documents in collection: {coll.estimated_document_count()}")
    client.close()


if __name__ == '__main__':
    main()
