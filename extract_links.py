#!/usr/bin/env python3
import re, glob, csv

files = sorted(glob.glob('bhavcopy_links/file_links_*.txt'))

with open('all_bhavcopy_links.csv', 'w', newline='') as out:
    writer = csv.writer(out)
    writer.writerow(['date', 'file_name', 'download_link'])

    for fpath in files:
        with open(fpath) as f:
            content = f.read()

        rows = re.findall(r'<tr class="bhavcopy-table-body">(.*?)</tr>', content)
        for row in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row)
            if len(tds) < 4:
                continue
            date = tds[1]
            # NSE column
            if tds[2] != '-':
                m = re.search(r'href="([^"]+)"[^>]*>([^<]+)</a>', tds[2])
                if m:
                    writer.writerow([date, m.group(2), m.group(1)])
            # BSE column
            if tds[3] != '-':
                m = re.search(r'href="([^"]+)"[^>]*>([^<]+)</a>', tds[3])
                if m:
                    writer.writerow([date, m.group(2), m.group(1)])

print("Done. Output: all_bhavcopy_links.csv")
