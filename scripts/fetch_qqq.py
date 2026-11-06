#!/usr/bin/env python3
"""Fetch QQQ daily bars and cash dividends from Nasdaq's public API (no key) and write qqq.json.

The chart uses dividend-adjusted closes so the line is a total-return series. Nasdaq's
chart endpoint has no CORS headers, so this runs in GitHub Actions rather than the browser.
"""
import datetime, json, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
FROM = "2020-01-01"
OUT = "qqq.json"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)

def utc_date(s):
    """Parse M/D/YYYY or YYYY-MM-DD as midnight UTC."""
    if "/" in s:
        m, d, y = s.split("/")
        y, m, d = int(y), int(m), int(d)
    else:
        y, m, d = (int(p) for p in s.split("-"))
    return datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)

def main():
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    chart = get(f"https://api.nasdaq.com/api/quote/QQQ/chart?assetclass=etf&fromdate={FROM}&todate={today}")
    bars = chart["data"]["chart"]
    rows = []
    for b in bars:
        z = b.get("z") or {}
        ts = b.get("x")
        close = z.get("close")
        if ts is None or close in (None, ""):
            continue
        close = float(str(close).replace(",", "").replace("$", ""))
        if not (ts > 0 and close > 0):
            continue
        rows.append([int(ts), close])
    rows.sort()
    # one bar per UTC day
    dedup = {}
    for ts, close in rows:
        dedup[ts] = close
    rows = sorted(dedup.items())
    if len(rows) < 1000 or rows[0][0] > datetime.datetime(2020, 1, 3, tzinfo=datetime.timezone.utc).timestamp() * 1000:
        raise SystemExit(f"unexpected QQQ chart: n={len(rows)} first={rows[:1]}")

    divj = get(f"https://api.nasdaq.com/api/quote/QQQ/dividends?assetclass=etf&fromdate={FROM}&todate={today}&limit=500")
    divs = []
    for r in divj["data"]["dividends"]["rows"]:
        if (r.get("type") or "").lower() != "cash":
            continue
        amt = float(str(r["amount"]).replace("$", "").replace(",", ""))
        if amt > 0:
            divs.append((int(utc_date(r["exOrEffDate"]).timestamp() * 1000), amt))

    adj = [c for _, c in rows]
    for ex_ts, amt in sorted(divs, reverse=True):
        i = next((k for k, (ts, _) in enumerate(rows) if ts >= ex_ts), None)
        if i is None or i == 0:
            continue
        prev = rows[i - 1][1]
        if prev <= amt:
            continue
        ratio = (prev - amt) / prev
        for j in range(i):
            adj[j] *= ratio

    out_rows = [[ts, round(a, 6), round(c, 4)] for (ts, c), a in zip(rows, adj)]
    # The newest bar is already ex any dividend on that session, so adjusted == close.
    if abs(out_rows[-1][1] - out_rows[-1][2]) > 0.02:
        raise SystemExit("adjusted close diverges from the latest close; dividend alignment looks wrong")
    try:
        prev = json.load(open(OUT))
    except (OSError, ValueError):
        prev = None
    if prev and prev.get("rows") == out_rows:
        print(f"unchanged ({len(out_rows)} bars through {utc_ms(out_rows[-1][0])})")
        return
    doc = {
        "symbol": "QQQ",
        "name": "Invesco QQQ Trust",
        "source": "Nasdaq public chart and dividend history (api.nasdaq.com, no API key)",
        "priceBasis": "adjClose is the traded close adjusted backward for cash dividends (total return, no split in this window). close is the session close.",
        "columns": ["t", "adjClose", "close"],
        "anchor": "2020-01-02",
        "fetchedUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": out_rows,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
        f.write("\n")
    print(f"wrote {len(out_rows)} bars {utc_ms(out_rows[0][0])} -> {utc_ms(out_rows[-1][0])}")
    print(f"anchor close {out_rows[0][2]} adj {out_rows[0][1]}")
    print(f"latest close {out_rows[-1][2]} adj {out_rows[-1][1]}")
    print(f"price return {(out_rows[-1][2]/out_rows[0][2]-1)*100:.2f}%  total return {(out_rows[-1][1]/out_rows[0][1]-1)*100:.2f}%")

def utc_ms(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).date().isoformat()

if __name__ == "__main__":
    main()
