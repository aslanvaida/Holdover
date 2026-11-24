"""A milk collection centre: the tank, the cooler, the backup and the generator.

Every number here is an editable assumption, not a measurement. They are sized for a typical 1,000 L village bulk milk
cooler and are what the prototype (mini fridge + sensor) is meant to check.
"""
from dataclasses import dataclass

from campus_energy_forecaster.outage import Backup

# Physical constants for raw milk.
MILK_DENSITY_KG_PER_L = 1.03
MILK_CP_KJ_PER_KG_K = 3.93

# Loads other than the cooler that the battery may or may not be asked to serve.
OPTIONAL_LOADS = ("lights", "office", "water_heater", "pump")
LOAD_LABELS = {"lights": "lights", "office": "office fan and computer", "water_heater": "water heater", "pump": "milk pump"}


@dataclass(frozen=True)
class Centre:
    name: str = "Simulated village milk centre"
    tank_litres: float = 1000.0
    ua_w_per_k: float = 15.0          # tank insulation: heat gain per degree of ambient-minus-milk difference
    cooling_kw_th: float = 6.5        # heat the cooler removes per hour when running (thermal kW)
    cop_at_25c: float = 3.0           # cooler efficiency (heat removed / electricity used) at 25 C ambient
    cop_drop_per_k: float = 0.04      # efficiency lost per degree of ambient above 25 C
    setpoint_c: float = 4.0           # normal holding temperature
    prechill_c: float = 2.0           # extra-cold setpoint before an expected cut
    safe_max_c: float = 8.0           # milk above this is at risk (EU Reg. 853/2004: <= 8 C when collected daily)
    chill_window_h: float = 3.0       # fresh milk must be back at or below safe_max_c within this many hours
    milk_in_c: float = 35.0           # temperature of fresh milk as it arrives
    charger_kw: float = 1.0           # battery recharge rate from the grid

    def cop(self, ambient_c: float) -> float:
        return max(1.2, self.cop_at_25c - self.cop_drop_per_k * (ambient_c - 25.0))


@dataclass(frozen=True)
class Generator:
    litres_per_hour: float = 1.3      # 5 kVA diesel set at part load
    diesel_usd_per_l: float = 1.05    # assumption; replace with the local pump price
    co2_kg_per_l: float = 2.68        # CO2 from burning one litre of diesel


# A small inverter battery bank: 4 x 12 V 150 Ah lead-acid = 7.2 kWh, of which half is usable.
DEFAULT_BACKUP = Backup(capacity_kwh=7.2, usable_fraction=0.5, efficiency=0.9)
