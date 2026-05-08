# ISIN Data source

## NSE

- Download from [NSE Link](https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv).
- Place the downloaded file as `isin_data/nse_isin_data.csv`.

## BSE

- Visit https://www.bseindia.com/corporates/List_Scrips.aspx
- Select Equity (T+1) rest all leave empty
- Click view & then download as csv
- Place the downloaded file as `isin_data/bse_isin_data.csv`

## Script

Finally, run the `build_isin_master.py` script. 

Output file is created as `isin_data/isin_master.csv`. 