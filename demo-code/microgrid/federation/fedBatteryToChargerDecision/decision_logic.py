"""Pure EV charging decision logic owned by the Battery twin.

No AWS calls, no I/O - just inputs -> outputs, so it can be reasoned about and
unit-tested on its own. The surrounding Strategy Lambda collects the inputs
(Collector + hot-reader pulls) and publishes the result through Feedback.

This is an ENERGY BALANCE, not a weighted formula: it splits the power that is
actually available between the EV and the battery, with the EV taking priority.

The car always comes first, from every source available; the battery gets only
what is left over. The two branches differ only in WHERE the energy comes from.

  green >= 75%  (renewables cheap - buy from the grid)
      available = gridMax * priceFactor + PV
      EV        = min(chargerMax, available)
      battery   = what the car could not take

  green < 75%   (grid brown/expensive - do not buy from it)
      available = batteryMaxDischarge + PV
      EV        = min(chargerMax, available)
      battery   = only the PV the car could not take
                  (never the battery's own discharge - it cannot charge itself)

The price only affects the green branch, because that is the only one that buys
energy from the grid. In the brown branch the energy comes from the battery and
from PV, both already paid for, so the price is irrelevant there.

The battery's own charge level is deliberately NOT part of the decision: it is
produced by the simulator, and a stray low value would silently turn a scenario
into 0 kW. Availability is assumed. It is still logged by the Strategy Lambda.
"""

# Share of renewables in the grid (%) at or above which grid energy is treated as
# cheap and green, so the grid is used to charge. Below it the grid counts as
# brown and is left untouched.
GREEN_ENERGY_THRESHOLD = 75.0

# Reference grid price, EUR/kWh. Roughly the Austrian household rate, and the
# point where the price has NO effect: at this value the factor is exactly 1.0,
# so the demo scenarios come out unchanged.
PRICE_BASELINE = 0.25
# Floor for the factor, so even an absurd price still allows some charging
# instead of dropping the car to zero.
MIN_PRICE_FACTOR = 0.3


def price_factor(electricity_price):
    """How much of the grid's capacity is worth buying at this price.

    1.0 at or below the baseline - cheaper energy does not let us exceed the
    hardware limits, so there is nothing to gain above 1.0. Above the baseline it
    falls off inversely: twice the price, half the draw.

    A missing or non-positive price (0.0 is what _as_float returns when the pull
    finds nothing) is treated as "no information" and leaves the split untouched,
    rather than silently behaving like free electricity.
    """
    if electricity_price is None or electricity_price <= 0.0:
        return 1.0
    return max(MIN_PRICE_FACTOR, min(1.0, PRICE_BASELINE / electricity_price))


def calculate_power_split(
    green_energy_percentage,
    pv_production,
    grid_max_power,
    charger_max_power,
    battery_max_charging_power,
    battery_max_discharging_power,
    is_plugged,
    electricity_price=None,
):
    """Return (actChargeEV, actBatteryCharge) in kW.

    actChargeEV      - what the Charger applies to the EV
    actBatteryCharge - what the battery charges ITSELF with
    """
    if not is_plugged:
        return 0.0, 0.0

    pv_production = max(0.0, pv_production)
    grid_max_power = max(0.0, grid_max_power)

    if green_energy_percentage >= GREEN_ENERGY_THRESHOLD:
        # Green: draw from the grid, but only as much of it as the price
        # justifies. The car is served FIRST from everything available - the
        # affordable grid share AND all PV - and only what it cannot take is
        # left for the battery.
        #
        # That is what keeps the car whole when the price rises: the grid share
        # shrinks, PV covers the gap, and the battery absorbs the shortfall.
        usable_grid = grid_max_power * price_factor(electricity_price)
        available = usable_grid + pv_production
        act_charge_ev = min(charger_max_power, available)
        battery_charge_power = min(
            battery_max_charging_power, max(0.0, available - act_charge_ev)
        )
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
