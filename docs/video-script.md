# Holdover: 2-minute video script (GSC Phase 1, Ignite)

**Theme:** Adaptation & Resilience: food resilience. The GSC template lists "% increase in access to … early warnings"
as an impact metric for this theme, and Holdover is an early warning. The diesel savings are a co-benefit. Last
cycle's Sustainable Energy winner was a solar cooling system (CoolFish), so this theme also avoids a head-to-head
comparison with it.

**Length:** about 275 spoken words, which is 2:00 at a calm 140 words a minute. If a practice run goes over, cut the
lines marked *(trim)*.

**Format:** voice-over on simple visuals. Nothing needs filming on location.

---

### 0:00–0:12 · Hook
**Visual:** a photo of milk cans or a village collection centre (a free stock photo, credited in the slides), with the
caption *6:00 pm*.

> Every evening at six, farmers across rural India and Kenya bring warm milk to a village cooling tank. And often,
> right then, the power goes out.

### 0:12–0:35 · Problem
**Visual:** a simple diagram: tank → battery → generator, with a big "?" over the battery. Then the WWF-India figure
on screen, with its source.

> The centre has a battery or a diesel generator, but nobody knows if it will last. So either the milk warms up, the
> dairy rejects it and farmers don't get paid, or the manager runs the generator all evening, just in case, burning
> money and diesel. WWF-India estimates erratic power costs at least three percent of the milk produced.

### 0:35–1:05 · Solution
**Visual:** four icons appear one by one (meter, sun/thermometer, calendar with a lightning bolt, tank). Then a phone
mock-up showing the SMS from `reports/alert_2026-06-03.txt`.

> Holdover is software that warns the manager the night before. It learns the centre's power use, checks the weather,
> and predicts the cut from the load-shedding schedule and past outages. Then it simulates the milk tank, minute by
> minute, through the cut, and finds the cheapest plan that keeps the milk safe. The manager gets one text message:
> switch off the lights and fan, run the generator from six to seven-thirty only *(trim: "or ask farmers to bring the
> milk in before the cut")*.

### 1:05–1:25 · Proof
**Visual:** a screen recording of `python scripts/run_demo.py` in a terminal, then the backtest table from the README.

> We've already built a working prototype, on top of our own energy forecaster. On a simulated milk centre over five
> weeks, doing nothing spoiled the milk on fourteen days. Following Holdover's plan: zero, using about a quarter of
> the diesel of running the generator through every cut.

### 1:25–1:45 · What's different
**Visual:** two columns. *Today:* "alarm after the milk is warm" / "new equipment". *Holdover:* "warning the night
before" / "the backup you already own".

> Tank alarms tell you once the milk is already warm. Solar chillers mean buying new equipment. Holdover needs no new
> hardware. It makes the backup a centre already owns go further, and pays for itself in diesel saved.

### 1:45–2:00 · Next and close
**Visual:** a sketch of the demo rig (mini fridge, jug of water, sensor, power bank). Then the title card: **Holdover**,
the team names, and github.com/aslanvaida/Holdover.

> Next, we test it on a real fridge rig and with a dairy cooperative, then take it to poultry fans and fish-farm
> aerators *(trim)*. Holdover: keep the milk cold, and the farmers paid.

---

### Notes
- **Keep it honest on camera.** Say "simulated" when giving the 14-to-0 result, and keep the README table visible. The
  judges can check the repo.
- **Show the sources.** Put "WWF-India, Dairy Cold Chain" on screen under the 3% figure, and put the full reference
  on the Supporting Materials slide.
- **Easiest recording:** one person reads the voice-over over a screen recording of slides made from the visuals
  above, using Keynote, Google Slides or PowerPoint export. Record the terminal clip separately and drop it in.
