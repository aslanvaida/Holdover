# Backtest: 2026-05-25 to 2026-06-28 (simulated centre)

All numbers come from the simulated centre in `holdover/simulate.py`, not from a real one. They show the method works
end to end and how its parts trade off, not what a real centre would save.

| | |
|---|---|
| Days | 35 |
| Days with a power cut | 16 |
| Cuts warned about the night before | 14 |
| Cuts not warned about (unscheduled faults) | 2 |
| Warnings with no cut (load-shedding skipped) | 1 |

**Days on which the milk went unsafe**

| Strategy | Days |
|---|---|
| As today (battery until flat, no generator) | 14 |
| Holdover plan (and as today on days with no warning) | 0 |
| Generator for the whole cut | 0 |

**Diesel on warned days:** Holdover 25.1 L vs 93.4 L running the generator for the whole
cut, saving 68.3 L (about $71.72, 183.0 kg CO2) over
14 cuts.

**Battery runtime, forecast the night before vs the real day** (nothing switched off, cuts that started on
schedule): mean absolute error 8 min, worst
15 min, over 12 cuts.

In this simulation the milk's "unsafe from" time is almost always set by the chilling rule (fresh evening milk must be
at or below 8 C within 3 hours of the last delivery), so it is 21:45 on most cut days; the battery runs out well before
the milk would warm up on its own. That is the main finding for the explainer: the risk is chilling the evening milk,
not keeping cold milk cold.
