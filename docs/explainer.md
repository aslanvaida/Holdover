# Holdover for Milk: GSC idea explainer

Holdover tells village milk centres the night before whether today's milk will stay cold through the next power cut,
and the cheapest thing to do so it does.

Code: https://github.com/aslanvaida/Holdover

## The problem

Milk centres have backup power, but they are guessing whether it will last.

- Small dairy farmers milk their cows twice a day, morning and evening.
- Fresh milk comes out at about body temperature (35°C), which suits bacteria.
- It must be chilled fast or it goes sour. EU rules require 8°C or below for milk collected daily, and centres
  usually aim for 4°C.
- Farmers bring their milk to a village collection centre with a big refrigerated tank, the bulk milk cooler. A truck
  takes it to the dairy later.

Where it goes wrong:

- In India, Kenya, Pakistan, Nigeria and South Africa, power cuts are common.
- When the power goes, the cooler switches to a battery or diesel generator, or it just stops.
- Nobody knows whether the backup will last until the power comes back.
- So either the milk warms and is rejected, and farmers aren't paid, or the centre runs the diesel generator through
  every cut "just in case", burning money and adding CO₂.

**The numbers.** WWF-India estimates that erratic electricity supply "leads to a loss of at least 3 per cent of the
milk produced". It also says diesel generators are the traditional backup, and that chilling takes 25–30% of a dairy
cooperative's energy use.[^wwf]

## Our solution

Holdover is software that answers one question for the milk centre manager: *if the power cuts out, will today's milk
stay cold, and if not, what is the cheapest thing to do right now?*

It needs no new hardware: it uses the centre's existing cooler, backup and meter. The answer arrives as one SMS or
WhatsApp message, with no app to install.

## How it works

1. **Learn the centre's power use.** It forecasts each circuit (cooler, lights, office, water heater, pump) hour by
   hour from the time and the weather. It uses the forecaster we already built for building electricity.
2. **Check the weather.** Hot days make the cooler less efficient and the milk warm faster.
3. **Predict the cut.** It uses the published load-shedding schedule plus what actually happened in that slot over
   the last 8 weeks: how often it happens, how long it usually lasts, and how long it can run on a bad day. It plans for
   the bad day.
4. **Simulate the milk tank** minute by minute through the cut:
   - warm milk mixes in as farmers arrive;
   - heat leaks in through the insulation;
   - the cooler runs on whatever power is left.

   Milk-safe time = how long the backup carries the cooler + how long the tank stays cold after the backup runs out.
5. **Find the cheapest plan.** It tries free actions first (switching off non-essential loads), then pre-chilling,
   then the shortest generator run that keeps the milk safe. It also checks whether asking farmers to come earlier
   would avoid the generator altogether.
6. **Send one SMS** to the centre manager.

## Example alert

This is real output from our working prototype, run on a simulated 1,000-litre centre (Wednesday load-shedding 17:00–21:00):

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

**What building it taught us.** The danger is chilling the fresh evening milk, not keeping cold milk cold:
- Bringing 470 L of milk down from 35°C takes about 6 kWh, roughly twice what a typical inverter battery can give.
- A well-insulated tank of milk that is already cold warms by less than 1°C an hour.

So the best actions are a short generator run while the evening milk comes in, or moving the evening collection
before the cut. Running the generator all evening wastes most of its fuel.

## What the centre can do with the warning

- Run the generator only when it is needed, which saves diesel money.
- Ask farmers to bring the evening milk in earlier, before the cut.
- Switch off non-essentials so the cooler gets all the backup power.
- Ask the milk truck to come earlier, or turn the milk into curd or ghee instead of losing it.
- Find out the backup is too small before it causes losses.

## What we already have

- **A working prototype**, open source at https://github.com/aslanvaida/Holdover. It includes the tank and power
  simulation, the outage forecast, the planner, the SMS text and tests.
- **The forecaster** it builds on, also ours:
  [campus-energy-forecaster](https://github.com/aslanvaida/campus-energy-forecaster). It predicts building electricity
  use with uncertainty bands and plans battery runtime during outages.

**First results, on a simulated centre over 35 days with 16 power cuts:**

| | Do nothing (battery until flat) | Holdover plan | Generator for every whole cut |
|---|---|---|---|
| Days the milk went unsafe | 14 | 0 | 0 |
| Diesel used | 0 L | 25 L | 93 L |

- Holdover warned about 14 of the 16 cuts the night before. The 2 it missed were short unscheduled faults, and the
  milk survived both.
- It forecast the battery runtime to within 8 minutes on average.

These results come from a simulation, not a real centre. They show the method works end to end. Measuring it on real
equipment is the next phase.

## What we'll build (Dec–Feb)

1. **Real data:** meter and tank-temperature data from a partner centre, and a live weather forecast.
2. **SMS/WhatsApp bot:** send the alert automatically every evening.
3. **A cheap demo rig** (about A$100–150), to measure our model's assumptions and test predicted against actual:
   - a mini fridge with a jug of water as the "milk", and a temperature sensor inside;
   - a power bank or battery as the "backup", and a smart plug for the "lights".

   We cut the power and compare the predicted and actual time until the water warms past the limit. Then we show
   that switching off the "lights", or running the "generator" for the right hour, extends it.
4. **User testing:** with a milk centre manager or dairy cooperative.

## Impact (how we'll measure it)

- Prediction accuracy: predicted vs actual safe hours and battery runtime
- Litres of milk saved per outage
- Money saved for farmers and centres
- Diesel litres and CO₂ saved (2.68 kg CO₂ per litre of diesel)

## Who pays

- **Dairy cooperatives and companies.** They own many collection centres and lose money when milk is rejected.
- **Milk centre operators.** A small monthly fee, paid back by diesel savings.

## What makes it different

- **Prediction, not alarms.** Tank monitors raise an alarm once the milk is already warm. Holdover warns the night
  before and says what to do.
- **Software, not hardware.** Solar and ice-bank chillers solve the problem by replacing equipment, which costs
  money. Holdover makes the backup a centre already has go further, so it works for the thousands of centres that will
  keep their diesel generator for years.

## Bigger picture

We start with milk and expand from there. The same engine (forecast the load, predict the cut, simulate what has to
stay powered, plan the cheapest fix) works for:
- poultry farms (fans);
- fish farms (aerators);
- hatcheries (incubators).

[^wwf]: WWF-India, Dairy Cold Chain, https://csp.wwfindia.org/dairy-cold-chain.php
