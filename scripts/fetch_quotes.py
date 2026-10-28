#!/usr/bin/env python3
"""Fetch STRC and SATA quotes from Nasdaq's public quote API (no key) and write quotes.json.
Runs server-side (GitHub Actions) because Nasdaq sends no CORS headers for browsers."""
import json, urllib.request, datetime, sys
SYMS = ["STRC", "SATA"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
def num(s):
    return float(str(s).replace("$", "").replace(",", "").replace("%", "").replace("+", "")) if s not in (None, "", "N/A") else None
def quote(sym, assetclass="stocks"):
    req = urllib.request.Request(f"https://api.nasdaq.com/api/quote/{sym}/info?assetclass={assetclass}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=20))["data"]
    p = d["primaryData"]
    return {"symbol": d["symbol"], "name": d["companyName"], "exchange": d.get("exchange"),
            "price": num(p["lastSalePrice"]), "change": num(p["netChange"]) if p.get("deltaIndicator") != "down" else -abs(num(p["netChange"])),
            "changePct": num(p["percentageChange"]) if p.get("deltaIndicator") != "down" else -abs(num(p["percentageChange"])),
            "asOf": p.get("lastTradeTimestamp"), "realTime": p.get("isRealTime"), "status": d.get("marketStatus")}

OPT_KEY, OPT_SYM = "IBIT_C50_2028-06", "IBIT280616C00050000"
def option_quote():
    """IBIT Jun 16 2028 $50 call from CBOE's public delayed-quotes chain (15-min delayed, no key)."""
    req = urllib.request.Request("https://cdn.cboe.com/api/global/delayed_quotes/options/IBIT.json",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    u = d["data"]
    if "IBIT" not in out["quotes"] and u.get("current_price"):
        out["quotes"]["IBIT"] = {"symbol": "IBIT", "name": "iShares Bitcoin Trust ETF", "price": u["current_price"],
            "change": u.get("price_change"), "changePct": u.get("price_change_percent"),
            "asOf": (u.get("last_trade_time") or "") + " ET", "status": "15-min delayed (CBOE)", "source": "CBOE"}
    o = next(x for x in d["data"]["options"] if x["option"] == OPT_SYM)
    return {"symbol": OPT_SYM, "name": "IBIT Jun 16 '28 $50 Call", "underlying": "IBIT",
            "underlyingPrice": d["data"].get("current_price"), "strike": 50.0, "expiry": "2028-06-16", "type": "call",
            "last": o.get("last_trade_price"), "lastTradeTime": o.get("last_trade_time"),
            "bid": o.get("bid"), "ask": o.get("ask"), "change": o.get("change"), "changePct": o.get("percent_change"),
            "volume": o.get("volume"), "openInterest": o.get("open_interest"), "iv": o.get("iv"),
            "asOfUtc": d.get("timestamp"), "delayed": "15-min delayed (CBOE)"}
out = {"fetchedUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Nasdaq", "quotes": {}}
for s in SYMS:
    try:
        out["quotes"][s] = quote(s)
    except Exception as e:
        print(f"{s}: {e}", file=sys.stderr)
try:  # IBIT ETF: Nasdaq first, CBOE chain underlying as fallback (set below)
    out["quotes"]["IBIT"] = dict(quote("IBIT", "etf"), source="Nasdaq")
except Exception as e:
    print(f"IBIT (Nasdaq): {e}", file=sys.stderr)
try:
    out["quotes"][OPT_KEY] = option_quote()
except Exception as e:  # fail soft: stocks still get written
    print(f"{OPT_KEY}: {e}", file=sys.stderr)
if not out["quotes"]:
    sys.exit("no quotes fetched")
json.dump(out, open("quotes.json", "w"), indent=1)
print(json.dumps(out, indent=1))
