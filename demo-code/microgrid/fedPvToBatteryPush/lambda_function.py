import json
from datetime import datetime, timezone

# Injected automatically by scripts/resolve_federation_push_target.py from
# Battery's (dtcsbat) deployed config_iot_devices.json, before "continue fed-sysml".
BATTERY_VIRTUAL_SENSOR_ID = "dRRRNfLuwgCbPwL8cNKM8Z"


def lambda_handler(event, context):
    print("Event: " + json.dumps(event))

    strategy_data = _collector_payload(event).get("dtc-PushUpdateStrategy", {})
    pv_data = strategy_data.get("production", {})
    pv_generated_power = pv_data.get("generatedPower", 0.0)

    return {
    "statusCode": 200,
    "body": json.dumps({
        "iotDeviceId": BATTERY_VIRTUAL_SENSOR_ID,
        "time": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "pvGeneratedPower": pv_generated_power
    })
    }


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
