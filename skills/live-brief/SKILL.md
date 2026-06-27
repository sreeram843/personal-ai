---
id: live-brief
name: Live data brief
description: Quick weather, markets, and headlines briefing
triggers:
  - live brief
  - morning briefing
  - daily brief
allowed_tools:
  - weather
  - market_price
  - get_crypto_price
  - news
---
When this skill is active, produce a concise briefing with these sections:
1. Weather for the user's implied location (ask if unknown)
2. Top market/crypto movers only when relevant to the query
3. 2-3 headline news items

Keep the entire response under 180 words unless the user asks for more detail.
Use live tools before guessing numbers.
