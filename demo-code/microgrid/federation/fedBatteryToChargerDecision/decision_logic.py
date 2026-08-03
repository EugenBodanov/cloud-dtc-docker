"""Pure EV charging decision logic owned by the Battery twin.

No AWS calls, no I/O - just inputs -> output, so it can be reasoned about and
unit-tested on its own. The surrounding Strategy Lambda collects the inputs
(Collector + hot-reader pulls) and publishes the result through Feedback.
"""
import math

# PV production (kW) that counts as a surplus: charge the EV with everything
# available. Must match dtcBattery's surplusThreshold #constAttribute - the SysML
# condition uses that const to decide WHETHER to fire, this decides WHAT to do.
#
# The Strategy Lambda cannot tell which event triggered it (the Step Function
# passes it only "$.collectorResult"), so the branch is chosen from the value
# itself. That gives the same answer either way.
SURPLUS_POINT = 47.5
# 47.5 is exactly representable in binary and PV computes it as 50.0 * 0.95,
# which lands on it exactly. The tolerance guards against a later tweak to the
# PV constants silently making the match never fire.
SURPLUS_TOLERANCE = 1e-6

# Share of renewables in the grid (%) above which the battery stores that energy
# for itself and the EV is told to stop charging. Must match dtcBattery's
# greenEnergyThreshold #constAttribute.
GREEN_ENERGY_THRESHOLD = 70.0

# Grid price bands, EUR/kWh.
CHEAP_PRICE = 0.15
EXPENSIVE_PRICE = 0.35
# The battery keeps this much charge (%) for itself before feeding the EV.
BATTERY_RESERVE_PERCENT = 20.0
# Share of available power used per price band. Deliberately BELOW 1.0: a later
# PV-surplus event must be able to raise actChargeEV, and it cannot if the
# ordinary calculation already saturates the available power.
CHEAP_POWER_SHARE = 0.5        # of the available power
NORMAL_POWER_SHARE = 0.25      # of PV production
EXPENSIVE_POWER_SHARE = 0.1    # of PV production - charge only from cheap PV


def is_at_surplus_point(generated_power):
    """True only at the PV surplus point (47.5 kW)."""
    return abs(generated_power - SURPLUS_POINT) <= SURPLUS_TOLERANCE


def calculate_charging_power(
    generated_power,
    green_energy_percentage,
    electricity_price,
    max_power,
    max_charging_power,
    battery_charge,
    is_plugged,
):
    """Return the charging power to apply to the EV, in kW. 0.0 = do not charge."""
    if not is_plugged:
        return 0.0

    # The EV can never draw more than the grid offers or the battery hardware
    # allows, whichever is lower.
    available = min(max_power, max_charging_power)
    if available <= 0.0:
        return 0.0

    # The battery protects its own reserve before serving the EV.
    if battery_charge < BATTERY_RESERVE_PERCENT:
        return 0.0

    # Checked BEFORE the surplus point: if both were somehow true at once, the
    # battery storing renewable energy for itself wins over charging the EV.
    if green_energy_percentage > GREEN_ENERGY_THRESHOLD:
        return 0.0

    if is_at_surplus_point(generated_power):
        # PV surplus: charge with everything available. Price is irrelevant -
        # the energy is locally produced. This is the one-time step up.
        power = available
    elif electricity_price >= EXPENSIVE_PRICE:
        # Expensive grid energy: charge only a small share of what PV produces.
        power = min(available, generated_power * EXPENSIVE_POWER_SHARE)
    elif electricity_price <= CHEAP_PRICE:
        # Cheap grid energy: worth topping up even when PV production is low.
        power = available * CHEAP_POWER_SHARE
    else:
        power = min(available, generated_power * NORMAL_POWER_SHARE)

    power = max(0.0, min(power, available))
    # Truncate rather than round: round() can push the result just above the
    # limit it was clamped to (e.g. 21.996 -> 22.0 when available is 21.996).
    return math.floor(power * 100.0) / 100.0
