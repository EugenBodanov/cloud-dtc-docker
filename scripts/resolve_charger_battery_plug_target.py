#!/usr/bin/env python3
"""Resolve the Battery isPlugged device ID from its deployed output and inject it
into the federation-owned Charger -> Battery plug push Lambda, before running
`continue fed-sysml`.

Standalone helper, not part of the orchestrator's command dispatch. Mirrors
scripts/resolve_grid_battery_push_target.py / resolve_grid_battery_maxpower_target.py
/ resolve_pv_battery_generatedpower_target.py. Run it after both dtcCharger and
dtcBattery have been deployed, and BEFORE `continue fed-sysml` - Terraform zips
whatever is on disk at that moment:

    python scripts/resolve_charger_battery_plug_target.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BATTERY_TWIN_NAME = "dtcBattery"
TARGET_PROPERTY_NAME = "isPlugged"
PLACEHOLDER = "__BATTERY_IS_PLUGGED_DEVICE_ID__"

BATTERY_DEVICES_FILE = (
    REPO_ROOT / "pipeline" / "digital-twin-manager" / "deployments"
    / BATTERY_TWIN_NAME / "input" / "config_iot_devices.json"
)
PUSH_LAMBDA_FILE = (
    REPO_ROOT / "demo-code" / "microgrid" / "federation"
    / "fedChargerToBatteryPlugPush" / "lambda_function.py"
)


def resolve_battery_is_plugged_device_id() -> str:
    if not BATTERY_DEVICES_FILE.is_file():
        raise SystemExit(
            f"Missing deployed device list: {BATTERY_DEVICES_FILE}. "
            f"Deploy '{BATTERY_TWIN_NAME}' before running federation."
        )

    devices = json.loads(BATTERY_DEVICES_FILE.read_text(encoding="utf-8"))
    for device in devices:
        for prop in device.get("properties", []):
            if prop.get("name") == TARGET_PROPERTY_NAME:
                return device["id"]

    raise SystemExit(
        f"No device with property '{TARGET_PROPERTY_NAME}' found in {BATTERY_DEVICES_FILE}. "
        f"Ensure isPlugged is declared in dtcBattery's storage component and "
        f"redeploy '{BATTERY_TWIN_NAME}'."
    )


def inject_into_push_lambda(device_id: str) -> None:
    if not PUSH_LAMBDA_FILE.is_file():
        raise SystemExit(f"Missing federation push Lambda: {PUSH_LAMBDA_FILE}")

    code = PUSH_LAMBDA_FILE.read_text(encoding="utf-8")
    updated = code.replace(f'"{PLACEHOLDER}"', f'"{device_id}"')

    if updated == code and PLACEHOLDER not in code:
        print(f"Already resolved: {PUSH_LAMBDA_FILE} references '{device_id}'.")
        return

    PUSH_LAMBDA_FILE.write_text(updated, encoding="utf-8")
    print(f"Injected Battery isPlugged device ID '{device_id}' into {PUSH_LAMBDA_FILE}")


def main() -> None:
    device_id = resolve_battery_is_plugged_device_id()
    inject_into_push_lambda(device_id)


if __name__ == "__main__":
    main()
