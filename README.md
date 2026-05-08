# Bhavcopy Pipeline

End-to-end pipeline to download, process, and ingest NSE/BSE daily bhavcopy data into MongoDB.

Data source: [Samco Bhavcopy](https://www.samco.in/bhavcopy-nse-bse-mcx)

## Pipeline Steps

### 1. Fetch bhavcopy links

```bash
bash onetime_bhav_samco.sh
```

Scrapes Samco's API month-by-month (from Jan 2016 onwards) and saves raw HTML responses to `bhavcopy_links/`.

### 2. Extract download links

```bash
python extract_links.py
```

Parses the HTML files in `bhavcopy_links/` and produces `all_bhavcopy_links.csv` with columns: `date`, `file_name`, `download_link`.

### 3. Download bhavcopy CSVs

```bash
python download_bhavcopy.py
```

Downloads all NSE and BSE bhavcopy CSV files into `raw_input_files/nse/` and `raw_input_files/bse/`. Skips already-downloaded files.

#### Retry helpers

- **`retry_empty_downloads.py`** — Re-downloads files under 1 KB using the original links from the CSV.
- **`retry_fresh_download.py`** — Re-fetches download links from Samco for failed dates and downloads fresh.

### 4. Build ISIN master

```bash
python build_isin_master.py
```

Merges NSE and BSE ISIN master files (`isin_data/nse_isin_data.csv`, `isin_data/bse_isin_data.csv`) into a unified lookup at `isin_data/isin_master.csv`. Only includes Indian equity ISINs (prefix `INE`).

### 5. Ingest into MongoDB

```bash
python ingest_to_mongodb_v3.py
```

Loads bhavcopy CSVs into MongoDB (`bhav.raw_bhav_data_v3`). Documents are bucketed monthly by ISIN with the structure:

```
_id: "{isin}_{yyyy-mm}"
i:   isin
d:   [ { dt, ex, sym, o, h, l, c, la, pc, tq, tv, tt, ... }, ... ]
```

Only data from 2021 onwards is ingested. Older versions (`ingest_to_mongodb.py`, `ingest_to_mongodb_v2.py`) are kept for reference.

## Directory Structure

```
bhavcopy_links/     # Raw HTML responses from Samco API
raw_input_files/
  nse/              # Downloaded NSE bhavcopy CSVs
  bse/              # Downloaded BSE bhavcopy CSVs
isin_data/          # ISIN master files (NSE, BSE, merged)
```

## Prerequisites

- Python 3
- MongoDB running on `localhost:27017`
- `pymongo` (`pip install pymongo`)

### Collection Creation command

```
db.createCollection("raw_bhav_data_v3", { storageEngine: { wiredTiger: { configString: "block_compressor=zstd" } } })
```