# Holdover

Holdover tells a village milk collection centre, the night before, whether today's milk will stay cold through the
next power cut and the cheapest way to make sure it does. It sends the answer as one SMS.

```
Holdover alert, Wed 03 Jun
Power cut likely 17:00-22:30, may run to 22:45 (75% of recent Wednesdays). Up to 36C.
Evening milk ~472 L at 18:00.
Battery lasts 2.0 h; milk unsafe from 21:45 if nothing is done.
Do this:
1. During the cut, switch off: lights, office fan and computer (battery lasts 0.3 h longer)
2. Run the generator 18:00-19:30 only, not the whole cut (saves ~5.5 L diesel)
Then milk stays safe.
Or: ask farmers to bring evening milk by 15:00; then no generator needed.
If power is not back by 22:45, run the generator until it is.
```

The output of `python scripts/run_demo.py` on the **simulated** centre. Every number in it is calculated, not
illustrative, but the centre is a simulation (see [Status](#status)).

## How it works

1. **Learns the centre's power use.** It forecasts each circuit (cooler, lights, office, water heater, pump) hour by
   hour from the time and the weather. It uses the quantile forecaster from
   [campus-energy-forecaster](https://github.com/aslanvaida/campus-energy-forecaster) unchanged, as a pinned
   dependency. Hours when the centre was on backup are gaps in the meter and are skipped.
2. **Reads the weather forecast.** Hot days make the cooler less efficient and the milk warm faster.
3. **Predicts the cut** from the published load-shedding schedule and what happened in the same slot over the last
   8 weeks: how often it happens, the usual length and the length it stays within on 9 days in 10. On hot days it
   stretches the length using the past link between temperature and overrun. Holdover plans for the 9-in-10 length.
4. **Simulates the milk tank** in 5-minute steps through the cut (`holdover/thermal.py`):
   - Warm milk mixes into the tank as farmers arrive.
   - Heat leaks in through the insulation.
   - The cooler removes heat when it has power, and its efficiency drops as the day gets hotter.
   - Power comes from the grid, then the generator, then the battery, and once the battery is flat there is none.

   Milk-safe time = how long the backup carries the cooler + how long the tank stays cold after the backup runs out.
5. **Finds the cheapest plan** (`holdover/planner.py`):
   - Free first: switch off non-essential loads while on battery.
   - Then pre-chill the tank to 2°C before the cut. This step is kept only if it shortens the generator run.
   - Then the shortest generator run that keeps the milk safe.

   It also checks the option that needs the farmers: bring the evening milk in before the cut. Plans are made against
   a limit 1°C below the real one, using the largest milk collection of the past week, so forecast errors have room.
6. **Writes the SMS** (`holdover/alert.py`).

## What the backtest shows

[`reports/backtest.md`](reports/backtest.md) covers 35 days on the simulated centre (25 May to 28 June 2026). It
forecasts at midnight each day, then replays the actual day under three strategies:

| | As today (battery until flat) | Holdover plan | Generator for the whole cut |
|---|---|---|---|
| Days the milk went unsafe | 14 | 0 | 0 |
| Diesel on the 14 warned cut days | 0 L | 25.1 L | 93.4 L |

- **Warnings:** 14 of 16 cuts were warned about the night before. The 2 missed were unscheduled faults, and the milk
  survived both. There was 1 false alarm.
- **Battery runtime forecast:** within 8 minutes on average of what actually happened (15 minutes at worst).
- **Diesel:** 68 L saved compared with running the generator for every cut, about $72 and 183 kg of CO2 over five
  weeks at the assumed prices.

**What the simulation taught us:** on almost every cut day, the risk is chilling the evening milk, not keeping cold
milk cold. Fresh milk at 35°C needs about 6 kWh of cooling, which is roughly twice what the battery holds. A
well-insulated tank of milk that is already cold warms only about 0.4–0.8°C an hour. So:
- the best action is a short generator run while the evening milk comes in, or bringing that milk in before the cut;
- pre-chilling the morning milk rarely helps.

The explainer's example alert should say this.

## Status

**What is real:**
- The thermal and power model, the planner, the outage forecast and the alert.
- The load forecaster, which comes from the campus project and was validated on real buildings there.

**What is simulated** (`holdover/simulate.py`, seeded, identical on every run):
- the centre's weather, milk volumes, loads and outages;
- the outage schedule, Mon/Wed/Fri 17:00–21:00, which happens 85% of the time and often runs late;
- the weather forecast: the actual weather plus about 1.5°C of error.

So the backtest shows that the method works end to end and how its parts trade off. It does not show what a real
centre would save. Because the "actual" days come from the same model, the 0 unsafe days for the Holdover plan is an
upper bound.

**Assumptions to measure** are all in `holdover/centre.py`:

| Assumption | Value |
|---|---|
| Tank | 1,000 L, insulation 15 W/K |
| Cooler | 6.5 kW of cooling |
| Cooler efficiency | 3.0 at 25°C, falling 0.04 per °C hotter |
| Battery | 7.2 kWh lead-acid, half of it usable |
| Generator | 1.3 L/h |
| Diesel price | $1.05/L |
| Safety rule | milk at or below 8°C (EU Reg. 853/2004, daily collection), with fresh milk allowed 3 h to come down |

The mini-fridge prototype is how we will measure the insulation and cooling numbers.

**Next:**
- real meter and temperature data from a centre;
- a real weather forecast API;
- recharging the battery from the generator;
- an SMS/WhatsApp gateway (for example Twilio);
- the prototype test of predicted vs actual time before the water passes 4°C.

## Run it

Needs Python 3.10+.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python scripts/run_demo.py                  # alert for Wed 3 June + what actually happened
python scripts/run_demo.py --day 2026-06-05
python scripts/backtest.py                  # reports/backtest.md and .json, about 10 s
pytest -q
```

## Layout

```
holdover/
  centre.py       the centre's equipment and every editable assumption
  thermal.py      5-minute tank temperature and power-source simulation
  simulate.py     the simulated centre (weather, milk, loads, outages, meter)
  forecasting.py  load forecasts (campus-energy-forecaster), weather and milk forecasts
  outages.py      cut prediction from the schedule and history
  planner.py      cheapest set of actions that keeps the milk safe
  alert.py        the SMS text
  pipeline.py     one day end to end, plus replaying the real day
scripts/          run_demo.py, backtest.py
reports/          generated alert and backtest results
tests/            physics, outage prediction and planner tests
```

## Licence

MIT
