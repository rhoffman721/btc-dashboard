#!/usr/bin/env python3
"""Fetch STRC and SATA quotes from Nasdaq's public quote API (no key) and write quotes.json.
Runs server-side (GitHub Actions) because Nasdaq sends no CORS headers for browsers."""
import json, urllib.request, datetime, sys
SYMS = ["STRC", "SATA"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
def num(s):
    return float(str(s).replace("$", "").replace(",", "").replace("%", "").replace("+", "")) if s not in (None, "", "N/A") else None
def quote(sym):
    req = urllib.request.Request(f"https://api.nasdaq.com/api/quote/{sym}/info?assetclass=stocks",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=20))["data"]
    p = d["primaryData"]
    return {"symbol": d["symbol"], "name": d["companyName"], "exchange": d.get("exchange"),
            "price": num(p["lastSalePrice"]), "change": num(p["netChange"]) if p.get("deltaIndicator") != "down" else -abs(num(p["netChange"])),
            "changePct": num(p["percentageChange"]) if p.get("deltaIndicator") != "down" else -abs(num(p["percentageChange"])),
            "asOf": p.get("lastTradeTimestamp"), "realTime": p.get("isRealTime"), "status": d.get("marketStatus")}
out = {"fetchedUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Nasdaq", "quotes": {}}
for s in SYMS:
    try:
        out["quotes"][s] = quote(s)
    except Exception as e:
        print(f"{s}: {e}", file=sys.stderr)
if not out["quotes"]:
    sys.exit("no quotes fetched")
json.dump(out, open("quotes.json", "w"), indent=1)
print(json.dumps(out, indent=1))
