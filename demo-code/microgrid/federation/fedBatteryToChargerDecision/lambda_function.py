import json
import os
from datetime import datetime, timedelta, timezone

import boto3

from decision_logic import calculate_charging_power

# Federation-owned Strategy Lambda for dtc-BatteryChargerDecisionStrategy.
#
# fed-sysml generates this function plus its Step Function, Collector, Feedback
# and IAM from the fedtwin.json entry. What fed-sysml cannot express is supplied
# by scripts/federate_battery_charger_decision.py AFTER `fed terraform apply`:
# the two hot-reader ARNs + lambda:InvokeFunction on them, the Charger target
# device id, and Battery's #constAttribute value (consts are not collectible).
GRID_HOT_READER_ARN = os.environ.get("GRID_HOT_READER_ARN")
GRID_WORKSPACE_ID = os.environ.get("GRID_WORKSPACE_ID")
GRID_ENTITY_ID = os.environ.get("GRID_ENTITY_ID")
GRID_SENSOR_COMPONENT = os.environ.get("GRID_SENSOR_COMPONENT")

BATTERY_HOT_READER_ARN = os.environ.get("BATTERY_HOT_READER_ARN")
BATTERY_WORKSPACE_ID = os.environ.get("BATTERY_WORKSPACE_ID")
BATTERY_ENTITY_ID = os.environ.get("BATTERY_ENTITY_ID")
BATTERY_STORAGE_COMPONENT = os.environ.get("BATTERY_STORAGE_COMPONENT")
BATTERY_EXTERNAL_INPUTS_COMPONENT = os.environ.get("BATTERY_EXTERNAL_INPUTS_COMPONENT")

CHARGER_ACT_CHARGE_DEVICE_ID = os.environ.get("CHARGER_ACT_CHARGE_DEVICE_ID")
BATTERY_MAX_CHARGING_POWER = os.environ.get("BATTERY_MAX_CHARGING_POWER")

STRATEGY_NAME = "dtc-BatteryChargerDecisionStrategy"
TRIGGER_EVENT_NAME = "plugDecision"

# How far back to look when reading the latest value of a property.
LOOKBACK_HOURS = 24

lambda_client = boto3.client("lambda")

REQUIRED_ENV = {
    "GRID_HOT_READER_ARN": GRID_HOT_READER_ARN,
    "GRID_WORKSPACE_ID": GRID_WORKSPACE_ID,
    "GRID_ENTITY_ID": GRID_ENTITY_ID,
    "GRID_SENSOR_COMPONENT": GRID_SENSOR_COMPONENT,
    "BATTERY_HOT_READER_ARN": BATTERY_HOT_READER_ARN,
    "BATTERY_WORKSPACE_ID": BATTERY_WORKSPACE_ID,
    "BATTERY_ENTITY_ID": BATTERY_ENTITY_ID,
    "BATTERY_STORAGE_COMPONENT": BATTERY_STORAGE_COMPONENT,
    "BATTERY_EXTERNAL_INPUTS_COMPONENT": BATTERY_EXTERNAL_INPUTS_COMPONENT,
    "CHARGER_ACT_CHARGE_DEVICE_ID": CHARGER_ACT_CHARGE_DEVICE_ID,
    "BATTERY_MAX_CHARGING_POWER": BATTERY_MAX_CHARGING_POWER,
}


def lambda_handler(event, context):
    print("Event: " + json.dumps(event))

    missing = [name for name, value in REQUIRED_ENV.items() if not value]
    if missing:
        raise RuntimeError(
            "Battery->Charger decision federation not fully established. Missing "
            f"env vars: {missing}. Run scripts/federate_battery_charger_decision.py "
            "after 'fed terraform apply'."
        )

    # What the Collector delivered - logged for diagnostics only. It is NOT used
    # as the source of truth: the Collector reads the hot-reader WITHOUT a time
    # range, which returns only the single latest DynamoDB record for the device.
    # dtcBattery.storage receives isPlugged (from the Charger federation) and
    # charge (from the simulator) in SEPARATE messages, so whichever arrived last
    # wins and the other property is simply absent from the Collector payload.
    collector = _collector_payload(event).get(STRATEGY_NAME, {}).get(TRIGGER_EVENT_NAME, {})
    print("DIAG collector payload: " + json.dumps(collector, default=str))

    # Everything is read explicitly with a time range, which makes the hot-reader
    # return every record containing the property, so a value is found regardless
    # of which message happened to be last.
    battery_storage = _pull(
        "Battery.storage", BATTERY_HOT_READER_ARN, BATTERY_WORKSPACE_ID,
        BATTERY_ENTITY_ID, BATTERY_STORAGE_COMPONENT,
        {"isPlugged": "STRING", "charge": "DOUBLE"},
    )
    battery_inputs = _pull(
        "Battery.externalInputs", BATTERY_HOT_READER_ARN, BATTERY_WORKSPACE_ID,
        BATTERY_ENTITY_ID, BATTERY_EXTERNAL_INPUTS_COMPONENT,
        {"generatedPower": "DOUBLE", "greenEnergyPercentage": "DOUBLE",
         "maxPower": "DOUBLE"},
    )
    # PULL / REQUEST to the Grid twin - the exchange mode. The price is used for
    # the decision only; it is deliberately not written back to Battery.
    grid_sensor = _pull(
        "Grid.sensor", GRID_HOT_READER_ARN, GRID_WORKSPACE_ID,
        GRID_ENTITY_ID, GRID_SENSOR_COMPONENT,
        {"currentElectricityPrice": "DOUBLE"},
    )

    is_plugged = _as_bool(battery_storage.get("isPlugged"))
    charge = _as_float(battery_storage.get("charge"))
    generated_power = _as_float(battery_inputs.get("generatedPower"))
    green_energy = _as_float(battery_inputs.get("greenEnergyPercentage"))
    max_power = _as_float(battery_inputs.get("maxPower"))
    electricity_price = _as_float(grid_sensor.get("currentElectricityPrice"))
    max_charging_power = _as_float(BATTERY_MAX_CHARGING_POWER)

    act_charge_ev = calculate_charging_power(
        generated_power=generated_power,
        green_energy_percentage=green_energy,
        electricity_price=electricity_price,
        max_power=max_power,
        max_charging_power=max_charging_power,
        battery_charge=charge,
        is_plugged=is_plugged,
    )

    print("DIAG inputs: " + json.dumps({
        "isPlugged": is_plugged, "charge": charge,
        "generatedPower": generated_power, "greenEnergyPercentage": green_energy,
        "maxPower": max_power, "electricityPrice": electricity_price,
        "maxChargingPower": max_charging_power,
    }))
    print("DIAG actChargeEV: " + json.dumps(act_charge_ev))

    # Feedback publishes this to dtcCharger/iot-data; ingestion routes by
    # iotDeviceId to write dtcCharger.chargerState.actChargeEV. The
    # {"statusCode", "body": json.dumps(...)} envelope is REQUIRED - the shared
    # Feedback Lambda reads strategyResult["body"] as a JSON string.
    return {
        "statusCode": 200,
        "body": json.dumps({
            "iotDeviceId": CHARGER_ACT_CHARGE_DEVICE_ID,
            "time": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "actChargeEV": act_charge_ev,
        }),
    }


def _pull(label, hot_reader_arn, workspace_id, entity_id, component_name, properties):
    """Read the latest value of each property from one component.

    Uses the hot-reader's TIME-RANGE branch on purpose. Without startTime/endTime
    the hot-reader returns only the single most recent DynamoDB record, and a
    property that arrived in an earlier message would be missing. With a range it
    returns every record containing the property, and the last entry is the newest
    (the DynamoDB query is ascending by timestamp).

    Note the two branches return DIFFERENT shapes: the time-range branch returns
    propertyValues as a LIST of {entityPropertyReference, values[]}, while the
    plain branch returns a DICT keyed by property name. This parses the list form.
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=LOOKBACK_HOURS)

    request_payload = {
        "workspaceId": workspace_id,
        "entityId": entity_id,
        "componentName": component_name,
        "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "selectedProperties": list(properties.keys()),
        "properties": {
            name: {"definition": {"dataType": {"type": data_type}}}
            for name, data_type in properties.items()
        },
    }

    try:
        response = lambda_client.invoke(
            FunctionName=hot_reader_arn,
            InvocationType="RequestResponse",
            Payload=json.dumps(request_payload).encode("utf-8"),
        )
        result = json.loads(response["Payload"].read())
    except Exception as error:  # noqa: BLE001 - a failed pull must not kill the run
        print(f"DIAG {label} pull failed: {error}")
        return {}

    print(f"DIAG raw {label} response: " + json.dumps(result, default=str)[:1500])

    values = {}
    property_values = result.get("propertyValues")
    if not isinstance(property_values, list):
        print(f"DIAG {label}: unexpected propertyValues shape, got {type(property_values)}")
        return values

    for entry in property_values:
        name = entry.get("entityPropertyReference", {}).get("propertyName")
        history = entry.get("values") or []
        if not name or not history:
            continue
        # Last entry is the newest - the DynamoDB query is ascending by time.
        raw_value = history[-1].get("value", {})
        if raw_value:
            values[name] = list(raw_value.values())[0]

    print(f"DIAG {label} resolved: " + json.dumps(values, default=str))
    return values


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes")


def _collector_payload(event):
    body = event.get("body")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    if isinstance(body, dict):
        return body
    return event
