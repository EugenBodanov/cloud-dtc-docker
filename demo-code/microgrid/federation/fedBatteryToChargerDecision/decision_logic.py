"""Pure EV charging decision logic owned by the Battery twin.

No AWS calls, no I/O - just inputs -> outputs, so it can be reasoned about and
unit-tested on its own. The surrounding Strategy Lambda collects the inputs
(Collector + hot-reader pulls) and publishes the result through Feedback.

This is an ENERGY BALANCE, not a weighted formula: it splits the power that is
actually available between the EV and the battery, with the EV taking priority.

  green >= 75%  (renewables cheap - draw from the grid)
      EV       = min(chargerMax, gridMax)
      battery  = min(batteryMaxCharge, leftover grid + PV)

  green < 75%   (grid brown/expensive - do not draw from it)
      EV       = min(chargerMax, batteryMaxDischarge + PV)   -- car has priority
      battery  = only the PV the car could not take

In the brown case the car is served first from BOTH sources: the battery
discharges into it and all PV goes the same way. The battery charges itself only
from whatever PV is left over once the car is full.

The battery's own charge level is deliberately NOT part of the decision: it is
produced by the simulator, and a stray low value would silently turn a scenario
into 0 kW. Availability is assumed. It is still logged by the Strategy Lambda.
"""

# Share of renewables in the grid (%) at or above which grid energy is treated as
# cheap and green, so the grid is used to charge. Below it the grid counts as
# brown and is left untouched.
GREEN_ENERGY_THRESHOLD = 75.0


def calculate_power_split(
    green_energy_percentage,
    pv_production,
    grid_max_power,
    charger_max_power,
    battery_max_charging_power,
    battery_max_discharging_power,
    is_plugged,
):
    """Return (actChargeEV, batteryChargePower) in kW.

    actChargeEV        - what the Charger applies to the EV
    batteryChargePower - what the battery charges ITSELF with
    """
    if not is_plugged:
        return 0.0, 0.0

    pv_production = max(0.0, pv_production)
    grid_max_power = max(0.0, grid_max_power)

    if green_energy_percentage >= GREEN_ENERGY_THRESHOLD:
        # Green and cheap: pull from the grid. The car has priority; whatever the
        # grid still has left, plus all PV production, goes into the battery.
        act_charge_ev = min(charger_max_power, grid_max_power)
        grid_left = max(0.0, grid_max_power - act_charge_ev)
        battery_charge_power = min(battery_max_charging_power, grid_left + pv_production)
    else:
        # Brown and expensive: do not touch the grid. The CAR has priority and is
        # fed from both sources at once - the battery discharges into it and all
        # PV goes the same way.
        act_charge_ev = min(charger_max_power, battery_max_discharging_power + pv_production)
        # Only the PV the car could not absorb is left for the battery.
        pv_taken_by_car = max(0.0, act_charge_ev - battery_max_discharging_power)
        pv_left = max(0.0, pv_production - pv_taken_by_car)
        battery_charge_power = min(battery_max_charging_power, pv_left)

    return _clamp(act_charge_ev, charger_max_power), _clamp(
        battery_charge_power, battery_max_charging_power
    )


def _clamp(value, upper):
    """Keep a power value inside [0, upper] and at two decimals.

    Truncates rather than rounds: round() can push a result just above the limit
    it was clamped to, and a power value must never exceed its hardware cap.
    """
    value = max(0.0, min(value, max(0.0, upper)))
    return int(value * 100.0) / 100.0
