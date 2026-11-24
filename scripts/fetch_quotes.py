#!/usr/bin/env python3
"""Fetch STRC and SATA quotes from Nasdaq's public quote API (no key) and write quotes.json.
Runs server-side (GitHub Actions) because Nasdaq sends no CORS headers for browsers."""
import json, urllib.request, datetime, sys, re
SYMS = ["STRC", "SATA"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
NASDAQ_HDRS = {"User-Agent": UA, "Accept": "application/json",
               "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com"}
def num(s):
    return float(str(s).replace("$", "").replace(",", "").replace("%", "").replace("+", "")) if s not in (None, "", "N/A", "--") else None
def quote(sym, assetclass="stocks"):
    """Nasdaq quote. Try assetclass, then the other of stocks/etf. Skip a null data/primaryData."""
    classes = [assetclass] + [c for c in ("stocks", "etf") if c != assetclass]
    last = None
    for ac in classes:
        try:
            req = urllib.request.Request(f"https://api.nasdaq.com/api/quote/{sym}/info?assetclass={ac}", headers=NASDAQ_HDRS)
            body = json.load(urllib.request.urlopen(req, timeout=20))
            d = body.get("data") if isinstance(body, dict) else None
            p = d.get("primaryData") if isinstance(d, dict) else None
            if d is None or p is None:
                msg = None
                try:
                    msg = body["status"]["bCodeMessage"][0]["errorMessage"]
                except (TypeError, KeyError, IndexError):
                    msg = None
                raise RuntimeError(msg or f"{sym}: no data for assetclass={ac}")
            return {"symbol": d["symbol"], "name": d["companyName"], "exchange": d.get("exchange"),
                    "price": num(p["lastSalePrice"]), "change": num(p["netChange"]) if p.get("deltaIndicator") != "down" else -abs(num(p["netChange"])),
                    "changePct": num(p["percentageChange"]) if p.get("deltaIndicator") != "down" else -abs(num(p["percentageChange"])),
                    "asOf": p.get("lastTradeTimestamp"), "realTime": p.get("isRealTime"), "status": d.get("marketStatus")}
        except Exception as e:
            last = e
    raise last if last is not None else RuntimeError(f"{sym}: no quote")

OPT_KEY, OPT_SYM = "IBIT_C50_2028-06", "IBIT280616C00050000"
def fill_ibit(price, source, change=None, changePct=None, asOf=None):
    """If the Nasdaq IBIT quote is missing, fill it from whichever option source succeeded."""
    if "IBIT" in out["quotes"] or not price:
        return
    venue = "CBOE" if source == "CBOE" else "Nasdaq"
    out["quotes"]["IBIT"] = {"symbol": "IBIT", "name": "iShares Bitcoin Trust ETF", "price": price,
        "change": change, "changePct": changePct, "asOf": asOf,
        "status": f"15-min delayed ({venue})", "source": source}
def option_quote():
    """IBIT Jun 16 2028 $50 call from CBOE's delayed chain, else Nasdaq's option chain."""
    try:
        req = urllib.request.Request("https://cdn.cboe.com/api/global/delayed_quotes/options/IBIT.json",
                                     headers={"User-Agent": UA, "Accept": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=30))
        u = d["data"]
        fill_ibit(u.get("current_price"), "CBOE", u.get("price_change"), u.get("price_change_percent"),
                  (u.get("last_trade_time") or "") + " ET")
        o = next(x for x in u["options"] if x["option"] == OPT_SYM)
        return {"symbol": OPT_SYM, "name": "IBIT Jun 16 '28 $50 Call", "underlying": "IBIT",
                "underlyingPrice": u.get("current_price"), "strike": 50.0, "expiry": "2028-06-16", "type": "call",
                "last": o.get("last_trade_price"), "lastTradeTime": o.get("last_trade_time"),
                "bid": o.get("bid"), "ask": o.get("ask"), "change": o.get("change"), "changePct": o.get("percent_change"),
                "volume": o.get("volume"), "openInterest": o.get("open_interest"), "iv": o.get("iv"),
                "asOfUtc": d.get("timestamp"), "delayed": "15-min delayed (CBOE)", "source": "CBOE"}
    except Exception as e:
        print(f"{OPT_KEY} (CBOE): {e}", file=sys.stderr)
        return option_quote_nasdaq()
def option_quote_nasdaq():
    """Exact IBIT Jun 16 2028 $50 call (OCC ...280616C00050000), not the 2027 $50 call."""
    req = urllib.request.Request(
        "https://api.nasdaq.com/api/quote/IBIT/option-chain?assetclass=stocks&fromdate=2028-06-16&todate=2028-06-16&money=all",
        headers=NASDAQ_HDRS)
    body = json.load(urllib.request.urlopen(req, timeout=30))
    data = body.get("data") if isinstance(body, dict) else None
    rows = ((data or {}).get("table") or {}).get("rows") or []
    row = next((r for r in rows if "280616c00050000" in str((r or {}).get("drillDownURL") or "").lower()), None)
    if row is None:
        raise RuntimeError(f"{OPT_SYM} not in Nasdaq option chain")
    last, bid, ask = num(row.get("c_Last")), num(row.get("c_Bid")), num(row.get("c_Ask"))
    if last is None and bid is None and ask is None:
        raise RuntimeError(f"{OPT_SYM}: no last/bid/ask")
    m = re.search(r"\$([0-9.,]+)", str((data or {}).get("lastTrade") or ""))
    underlying = num(m.group(1)) if m else None
    fill_ibit(underlying, "Nasdaq")
    return {"symbol": OPT_SYM, "name": "IBIT Jun 16 '28 $50 Call", "underlying": "IBIT",
            "underlyingPrice": underlying, "strike": 50.0, "expiry": "2028-06-16", "type": "call",
            "last": last, "lastTradeTime": None, "bid": bid, "ask": ask, "change": num(row.get("c_Change")),
            "changePct": None, "volume": num(row.get("c_Volume")), "openInterest": num(row.get("c_Openinterest")),
            "iv": None, "asOfUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "delayed": "15-min delayed (Nasdaq)", "source": "Nasdaq"}
out = {"fetchedUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Nasdaq", "quotes": {}}
for s in SYMS:
    try:
        out["quotes"][s] = quote(s)
    except Exception as e:
        print(f"{s}: {e}", file=sys.stderr)
try:  # IBIT: Nasdaq stock quote (ETF class no longer resolves); option chain underlying is the fallback
    out["quotes"]["IBIT"] = dict(quote("IBIT", "stocks"), source="Nasdaq")
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
