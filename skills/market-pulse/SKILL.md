---
id: market-pulse
name: Market pulse
description: Live equities, crypto, and FX check for a portfolio or ticker
triggers:
  - market pulse
  - portfolio check
allowed_tools:
  - market_price
  - get_crypto_price
  - fx_rate
---
When this skill is active, fetch live prices before answering.
Use market_price for equities and indices, get_crypto_price for crypto, and fx_rate for currencies.
Lead with the numbers the user asked about. Ask for the ticker, pair, or holdings list if it is missing.
