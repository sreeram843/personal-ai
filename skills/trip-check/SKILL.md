---
id: trip-check
name: Trip check
description: Live flight, traffic, transit, and weather status for a trip
triggers:
  - trip check
  - travel status
allowed_tools:
  - get_flight_status
  - get_traffic_eta
  - get_transit_arrivals
  - weather
---
When this skill is active, check live travel conditions before answering.
Use get_flight_status for flights, get_traffic_eta for driving, get_transit_arrivals for transit, and weather for the route or destination.
Ask for the missing flight number, origin/destination, or time window.
Keep the answer operational: status, delays, and what to do next.
