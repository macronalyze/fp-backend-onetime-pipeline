#!/usr/bin/env bash

set -euo pipefail

START_YEAR=2016
START_MONTH=1
TODAY="$(date +%F)"
OUT_DIR="bhavcopy_links"

mkdir -p "$OUT_DIR"

year="$START_YEAR"
month="$START_MONTH"

while :; do
  month_padded="$(printf "%02d" "$month")"
  month_start="$(printf "%04d-%02d-01" "$year" "$month")"
  month_end="$(date -j -v"${month}"m -v1d -v"${year}"y -v+1m -v-1d +%F)"

  [[ "$month_start" > "$TODAY" ]] && break
  [[ "$month_end" > "$TODAY" ]] && month_end="$TODAY"

  out_file="$OUT_DIR/file_links_${month_padded}_${year}.txt"

  if [[ -f "$out_file" ]]; then
    echo "Skipping existing file: $out_file"
  else
    echo "Fetching ${month_start} to ${month_end} -> ${out_file}"

    curl --fail --silent --show-error \
      'https://www.samco.in/bse_nse_mcx/getBhavcopy' \
      -H 'Accept: text/html, */*; q=0.01' \
      -H 'Accept-Language: en-US,en;q=0.9' \
      -H 'Connection: keep-alive' \
      -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8' \
      -b '_gcl_au=1.1.550583118.1778208733; _ga=GA1.1.1503152860.1778208733; _twpid=tw.1778208733598.515601899227772692; _fbp=fb.1.1778208733974.566150658206845180; _clck=h36nnq%5E2%5Eg5v%5E0%5E2319; ci_session=fn5986bic2k0na3m9nrbgs6jtagurhcr; _uetsid=e90f47f04a8811f1ac8c4b240d8b377f; _uetvid=e90f74404a8811f1931f6b1e3d456137; _clsk=1rf57zy%5E1778210994379%5E1%5E1%5Ev.clarity.ms%2Fcollect; _ga_YF9VV754Z4=GS2.1.s1778210992$o2$g1$t1778211005$j47$l0$h0; _ga_DY5XK74QYC=GS2.1.s1778211017$o1$g1$t1778211095$j60$l0$h0; _ga_Z1GWTLJBB8=GS2.1.s1778210992$o2$g1$t1778211193$j60$l0$h0' \
      -H 'Origin: https://www.samco.in' \
      -H 'Referer: https://www.samco.in/bhavcopy-nse-bse-mcx' \
      -H 'Sec-Fetch-Dest: empty' \
      -H 'Sec-Fetch-Mode: cors' \
      -H 'Sec-Fetch-Site: same-origin' \
      -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
      -H 'X-Requested-With: XMLHttpRequest' \
      -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
      -H 'sec-ch-ua-mobile: ?0' \
      -H 'sec-ch-ua-platform: "macOS"' \
      --retry 3 \
      --retry-delay 2 \
      --data-raw "start_date=${month_start}&end_date=${month_end}&bhavcopy_data%5B%5D=NSE&bhavcopy_data%5B%5D=BSE&show_or_down=1" \
      -o "$out_file"
  fi

  sleep_seconds=$(( RANDOM % 6 + 3 ))
  echo "Sleeping ${sleep_seconds}s..."
  sleep "$sleep_seconds"

  month=$((month + 1))
  if [[ "$month" -gt 12 ]]; then
    month=1
    year=$((year + 1))
  fi
done

echo "Done. Files saved in ${OUT_DIR}/"
