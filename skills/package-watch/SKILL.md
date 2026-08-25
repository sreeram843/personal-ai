---
id: package-watch
name: Package watch
description: Live carrier tracking status for a shipment
triggers:
  - where's my package
  - where is my package
  - delivery status
allowed_tools:
  - get_package_tracking
---
When this skill is active, look up the shipment with get_package_tracking.
Ask for the carrier and tracking number if either is missing.
Lead with current status, last scan, and ETA.
