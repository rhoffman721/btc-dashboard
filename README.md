# btc-dashboard

Static single-page Bitcoin dashboard, live at https://rhoffman721.github.io/btc-dashboard/.

![Bitcoin dashboard](preview.png)

- Live BTC price and 24h change (CoinGecko, falling back to Coinbase/Kraken).
- Power-law fair value `10^-17.016 * d^5.84` and floor `10^-17.351 * d^5.84` (`d` = days since 2009-01-03).
- Log-scale history chart from 2010 with a 200-day SMA and dashed projections to 2030.
- 60s auto-refresh.

GitHub Pages: Deploy from branch `main`, folder `/ (root)`.
