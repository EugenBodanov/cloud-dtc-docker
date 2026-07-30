#!/usr/bin/env python3
"""Resolve the Battery virtual sensor ID from its deployed output and inject it
into the federation-owned push Lambda, before running `continue fed-sysml`.

This is a standalone helper, not part of the orchestrator's command dispatch.
Run it manually after both dtcspv and dtcsbat have been deployed:

    python scripts/resolve_federation_push_target.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BATTERY_TWIN_NAME = "dtc2bat"
TARGET_PROPERTY_NAME = "pvGeneratedPower"
PLACEHOLDER = "__BATTERY_VIRTUAL_SENSOR_ID__"

BATTERY_DEVICES_FILE = (
    REPO_ROOT / "pipeline" / "digital-twin-manager" / "deployments"
    / BATTERY_TWIN_NAME / "input" / "config_iot_devices.json"
)
PUSH_LAMBDA_FILE = (
    REPO_ROOT / "demo-code" / "microgrid" / "fedPvToBatteryPush" / "lambda_function.py"
)


def resolve_battery_virtual_sensor_id() -> str:
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
        f"No device with property '{TARGET_PROPERTY_NAME}' found in {BATTERY_DEVICES_FILE}."
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
    print(f"Injected Battery virtual sensor ID '{device_id}' into {PUSH_LAMBDA_FILE}")


def main() -> None:
    device_id = resolve_battery_virtual_sensor_id()
    inject_into_push_lambda(device_id)


if __name__ == "__main__":
    main()
