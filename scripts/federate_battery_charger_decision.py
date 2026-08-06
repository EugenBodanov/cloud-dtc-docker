#!/usr/bin/env python3
"""Federation enablement step for dtc-BatteryChargerDecisionStrategy.

The bulk of this federation is REAL fed-sysml: the fedtwin.json entry
(referencing dtcBattery.plugDecision) makes `continue fed-sysml` +
`fed terraform apply` generate the Event Registry trigger, Step Function,
Collector, Strategy Lambda, Feedback Lambda and their IAM roles - all in
Terraform.

Three things fed-sysml structurally cannot express are supplied here, targeting
the FEDERATION-OWNED Strategy Lambda (never a twin):

  1. The hot-reader coordinates for dtcGrid (electricity price PULL) and for
     dtcBattery itself (the pushed values + charge), plus lambda:InvokeFunction
     scoped to exactly those two hot-readers. fed-sysml grants the Strategy role
     logs-only IAM, and the Collector only fetches the triggering
     strategyAction's own inputParameters.
  2. The Charger target device id for the Feedback payload.
  3. dtcBattery's #constAttribute maxChargingPower - consts are not collectible
     (same reason PV_MAX_POWER is env-injected in fedPvWeatherRequest).

The fed-sysml Strategy Lambda + role names are deterministic
(<strategyName>_strategy / <strategyName>_strategy-role), so no discovery is
needed. Runs automatically at the end of `fed terraform apply` (see
scripts/orchestrator/pipeline.py).

    python scripts/federate_battery_charger_decision.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

GRID_TWIN_NAME = "dtcGrid"
BATTERY_TWIN_NAME = "dtcBattery"
CHARGER_TWIN_NAME = "dtcCharger"

# Properties used to identify which component is which, via device -> component.
GRID_PRICE_PROPERTY = "currentElectricityPrice"
BATTERY_STORAGE_PROPERTY = "charge"
BATTERY_EXTERNAL_INPUTS_PROPERTY = "generatedPower"
CHARGER_ACT_CHARGE_PROPERTY = "actChargeEV"
# #constAttribute values read from their deployed initValue - consts cannot be
# fetched through the Collector.
BATTERY_CONSTS = {
    "BATTERY_MAX_CHARGING_POWER": "maxChargingPower",
    "BATTERY_MAX_DISCHARGING_POWER": "maxDischargingPower",
}
CHARGER_CONSTS = {
    "CHARGER_MAX_POWER": "maxPower",
}

STRATEGY_NAME = "dtc-BatteryChargerDecisionStrategy"
STRATEGY_FUNCTION_NAME = f"{STRATEGY_NAME}_strategy"
STRATEGY_ROLE_NAME = f"{STRATEGY_NAME}_strategy-role"
INVOKE_POLICY_NAME = "battery-charger-decision-invoke"


def _deployment_file(twin: str, *parts: str) -> Path:
    return REPO_ROOT / "pipeline" / "digital-twin-manager" / "deployments" / twin / Path(*parts)


def _load(twin: str, *parts: str) -> object:
    path = _deployment_file(twin, *parts)
    if not path.is_file():
        raise SystemExit(
            f"Missing deployed file: {path}. "
            f"Deploy '{twin}' independently before running federation."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Discovery (local, read-only)
# --------------------------------------------------------------------------- #
def _device_id_for_property(devices: list, property_name: str, twin: str) -> str:
    for device in devices:
        for prop in device.get("properties", []):
            if prop.get("name") == property_name:
                return device["id"]
    raise SystemExit(
        f"No device with property '{property_name}' found for '{twin}'. "
        f"Redeploy '{twin}' and try again."
    )


def _component_name_for_device(hierarchy: list, device_id: str, twin: str) -> str:
    for child in hierarchy[0].get("children", []):
        if child.get("iotDeviceId") == device_id:
            return child["name"]
    raise SystemExit(
        f"Could not resolve the component name for device '{device_id}' in '{twin}'."
    )


def discover_twin_components(twin: str, properties: dict) -> dict:
    """Return hot-reader coordinates plus a component name per requested property."""
    federation_input = _load(twin, "output", f"{twin}_federation_input.json")
    hierarchy = _load(twin, "input", "config_hierarchy.json")
    devices = _load(twin, "input", "config_iot_devices.json")

    if not hierarchy:
        raise SystemExit(f"Empty hierarchy for '{twin}'.")

    resolved = {
        "hot_reader_arn": federation_input["hot_reader_arn"],
        "workspace_id": federation_input["twinmaker_workspace_id"],
        "entity_id": hierarchy[0]["id"],
        "region": federation_input["region"],
    }
    for key, property_name in properties.items():
        device_id = _device_id_for_property(devices, property_name, twin)
        resolved[key] = _component_name_for_device(hierarchy, device_id, twin)
    return resolved


def discover_charger_act_charge_device_id() -> str:
    devices = _load(CHARGER_TWIN_NAME, "input", "config_iot_devices.json")
    return _device_id_for_property(
        devices, CHARGER_ACT_CHARGE_PROPERTY, CHARGER_TWIN_NAME
    )


def discover_consts(twin: str, wanted: dict) -> dict:
    """Read #constAttribute initValues from a twin's deployed config.

    Consts are not collectible at runtime, so their values are injected as env
    vars instead (same reason PV_MAX_POWER is injected in fedPvWeatherRequest).
    """
    devices = _load(twin, "input", "config_iot_devices.json")
    found = {}
    for device in devices:
        for prop in device.get("properties", []):
            for env_name, const_name in wanted.items():
                if prop.get("name") == const_name and "initValue" in prop:
                    found[env_name] = str(prop["initValue"])

    missing = [c for e, c in wanted.items() if e not in found]
    if missing:
        raise SystemExit(
            f"No const with an initValue found for {missing} in '{twin}'. Ensure "
            f"they are declared at the #entity level in {twin}.sysml "
            "(constAttributes inside a #component are dropped) and redeploy."
        )
    return found


# --------------------------------------------------------------------------- #
# AWS: enable the fed-sysml-generated Strategy Lambda
# --------------------------------------------------------------------------- #
def inject_env(lambda_client, new_env: dict) -> None:
    try:
        current = lambda_client.get_function_configuration(FunctionName=STRATEGY_FUNCTION_NAME)
    except lambda_client.exceptions.ResourceNotFoundException:
        raise SystemExit(
            f"Strategy Lambda '{STRATEGY_FUNCTION_NAME}' not found. Run "
            "'continue fed-sysml' + 'fed terraform apply' first, then this step."
        )

    variables = dict(current.get("Environment", {}).get("Variables", {}))
    variables.update(new_env)
    lambda_client.update_function_configuration(
        FunctionName=STRATEGY_FUNCTION_NAME,
        Environment={"Variables": variables},
    )
    lambda_client.get_waiter("function_updated").wait(FunctionName=STRATEGY_FUNCTION_NAME)
    print(f"Injected env vars into {STRATEGY_FUNCTION_NAME}")


def grant_invoke(iam, hot_reader_arns: list) -> None:
    """Scope InvokeFunction to exactly the hot-readers this Strategy reads."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunction"],
            "Resource": hot_reader_arns,
        }],
    }
    try:
        iam.put_role_policy(
            RoleName=STRATEGY_ROLE_NAME,
            PolicyName=INVOKE_POLICY_NAME,
            PolicyDocument=json.dumps(policy),
        )
    except iam.exceptions.NoSuchEntityException:
        raise SystemExit(
            f"Strategy role '{STRATEGY_ROLE_NAME}' not found. Run "
            "'continue fed-sysml' + 'fed terraform apply' first."
        )
    print(f"Granted lambda:InvokeFunction on {hot_reader_arns} to {STRATEGY_ROLE_NAME}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    print("Running Battery->Charger decision federation enablement step...")

    grid = discover_twin_components(GRID_TWIN_NAME, {"sensor": GRID_PRICE_PROPERTY})
    battery = discover_twin_components(BATTERY_TWIN_NAME, {
        "storage": BATTERY_STORAGE_PROPERTY,
        "external_inputs": BATTERY_EXTERNAL_INPUTS_PROPERTY,
    })
    charger_device_id = discover_charger_act_charge_device_id()
    battery_consts = discover_consts(BATTERY_TWIN_NAME, BATTERY_CONSTS)
    charger_consts = discover_consts(CHARGER_TWIN_NAME, CHARGER_CONSTS)

    try:
        import boto3
    except ImportError:
        raise SystemExit(
            "boto3 is required for this enablement step. Install it "
            "(pip install boto3) and ensure AWS credentials are set."
        )

    region = battery["region"]
    lambda_client = boto3.client("lambda", region_name=region)
    iam = boto3.client("iam", region_name=region)

    env = {
        "GRID_HOT_READER_ARN": grid["hot_reader_arn"],
        "GRID_WORKSPACE_ID": grid["workspace_id"],
        "GRID_ENTITY_ID": grid["entity_id"],
        "GRID_SENSOR_COMPONENT": grid["sensor"],
        "BATTERY_HOT_READER_ARN": battery["hot_reader_arn"],
        "BATTERY_WORKSPACE_ID": battery["workspace_id"],
        "BATTERY_ENTITY_ID": battery["entity_id"],
        "BATTERY_STORAGE_COMPONENT": battery["storage"],
        "BATTERY_EXTERNAL_INPUTS_COMPONENT": battery["external_inputs"],
        "CHARGER_ACT_CHARGE_DEVICE_ID": charger_device_id,
        **battery_consts,
        **charger_consts,
    }

    # Grant first, then inject: once env is present the Strategy Lambda will
    # attempt both pulls, so the permissions should already be in place.
    grant_invoke(iam, [grid["hot_reader_arn"], battery["hot_reader_arn"]])
    inject_env(lambda_client, env)

    print("Battery->Charger decision federation enablement complete.")


if __name__ == "__main__":
    main()
