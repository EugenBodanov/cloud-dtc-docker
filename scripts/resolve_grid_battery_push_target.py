#!/usr/bin/env python3
"""Resolve the Battery greenEnergyPercentage device ID from its deployed
output and (re)generate the federation-owned Grid -> Battery push Lambda
from its template, before running `continue fed-sysml`.

This is a standalone helper, not part of the orchestrator's command
dispatch, mirroring scripts/resolve_federation_push_target.py for the
dtcGrid/dtcBattery pair. Run it manually after both dtcGrid and dtcBattery
have been deployed:

    python3 scripts/resolve_grid_battery_push_target.py
"""
from __future__ import annotations

from resolve_common import REPO_ROOT, resolve_and_inject

BATTERY_TWIN_NAME = "dtcBattery"
TARGET_PROPERTY_NAME = "greenEnergyPercentage"
PLACEHOLDER = "__BATTERY_GREEN_ENERGY_DEVICE_ID__"

LAMBDA_DIR = (
    REPO_ROOT / "demo-code" / "microgrid" / "federation" / "fedGridToBatteryPush"
)


def main() -> None:
    resolve_and_inject(
        source_twin=BATTERY_TWIN_NAME,
        property_name=TARGET_PROPERTY_NAME,
        placeholder=PLACEHOLDER,
        template_file=LAMBDA_DIR / "lambda_function.py.template",
        target_file=LAMBDA_DIR / "lambda_function.py",
        label="Battery greenEnergyPercentage device ID",
    )


if __name__ == "__main__":
    main()
