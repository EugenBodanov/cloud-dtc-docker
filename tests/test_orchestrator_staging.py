from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.orchestrator import staging


class OrchestratorStagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pipeline_root = Path(self.temp_dir.name) / "pipeline"
        self.manager_input = self.pipeline_root / "digital-twin-manager" / "input"
        self.manager_output = self.pipeline_root / "digital-twin-manager" / "output"
        self.manager_deployments = self.pipeline_root / "digital-twin-manager" / "deployments"
        self.federation_input = self.pipeline_root / "fed-sysml" / "input"
        self.federation_output = self.pipeline_root / "fed-sysml" / "output"

        for path in (
            self.manager_input,
            self.manager_output,
            self.manager_deployments,
            self.federation_input / "strategyInputs",
            self.federation_output,
        ):
            path.mkdir(parents=True, exist_ok=True)

        self.original_paths = {
            "PIPELINE_ROOT": staging.PIPELINE_ROOT,
            "MANAGER_INPUT_DIR": staging.MANAGER_INPUT_DIR,
            "MANAGER_OUTPUT_DIR": staging.MANAGER_OUTPUT_DIR,
            "MANAGER_DEPLOYMENTS_DIR": staging.MANAGER_DEPLOYMENTS_DIR,
            "FEDERATION_INPUT_DIR": staging.FEDERATION_INPUT_DIR,
            "FEDERATION_OUTPUT_DIR": staging.FEDERATION_OUTPUT_DIR,
        }
        staging.PIPELINE_ROOT = self.pipeline_root
        staging.MANAGER_INPUT_DIR = self.manager_input
        staging.MANAGER_OUTPUT_DIR = self.manager_output
        staging.MANAGER_DEPLOYMENTS_DIR = self.manager_deployments
        staging.FEDERATION_INPUT_DIR = self.federation_input
        staging.FEDERATION_OUTPUT_DIR = self.federation_output

    def tearDown(self) -> None:
        for name, value in self.original_paths.items():
            setattr(staging, name, value)
        self.temp_dir.cleanup()

    def write_json(self, path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_fedtwin(self, strategy_refs: list[str]) -> Path:
        path = self.federation_input / "fedtwin.json"
        self.write_json(
            path,
            {
                "fedTwins": [
                    {
                        "name": "MicroGrid",
                        "newStrategies": [
                            {
                                "name": "ConsumptionStrategy",
                                "strategies": strategy_refs,
                            }
                        ],
                    }
                ]
            },
        )
        return path

    def write_broker_config(self) -> None:
        self.write_json(self.federation_input / "brokerConfig.json", {"brokers": {}})

    def test_required_twins_accepts_one_twin_with_multiple_strategies(self) -> None:
        fedtwin = self.write_fedtwin(["dtc-y-03.stopCharging", "dtc-y-03.stopChargingP14"])

        self.assertEqual(staging.required_twins_from_fedtwin(fedtwin), ["dtc-y-03"])

    def test_required_twins_deduplicates_two_twin_references(self) -> None:
        fedtwin = self.write_fedtwin(["PV.production", "Battery.status", "PV.production"])

        self.assertEqual(staging.required_twins_from_fedtwin(fedtwin), ["PV", "Battery"])

    def test_required_twins_rejects_invalid_strategy_reference(self) -> None:
        fedtwin = self.write_fedtwin(["PV"])

        with self.assertRaises(SystemExit):
            staging.required_twins_from_fedtwin(fedtwin)

    def test_save_manager_deployment_artifact_copies_current_twin_output(self) -> None:
        self.write_json(self.manager_input / "config.json", {"digital_twin_name": "PV"})
        self.write_json(self.manager_output / "PV_federation_input.json", {"name": "PV"})
        self.write_json(self.manager_output / "Battery_federation_input.json", {"name": "Battery"})
        auth_dir = self.manager_output / "iot_devices_auth"
        auth_dir.mkdir()
        (auth_dir / "device.json").write_text("{}", encoding="utf-8")

        saved_artifact = staging.save_manager_deployment_artifact()

        self.assertEqual(saved_artifact, self.manager_deployments / "PV" / "PV_federation_input.json")
        self.assertTrue(saved_artifact.is_file())
        self.assertTrue((self.manager_deployments / "PV" / "iot_devices_auth" / "device.json").is_file())
        self.assertFalse((self.manager_deployments / "PV" / "Battery_federation_input.json").exists())

    def test_stage_federation_inputs_uses_only_twins_from_fedtwin(self) -> None:
        self.write_fedtwin(["PV.production", "Battery.status"])
        self.write_broker_config()
        self.write_json(self.manager_deployments / "PV" / "PV_federation_input.json", {"name": "PV"})
        self.write_json(self.manager_deployments / "Battery" / "Battery_federation_input.json", {"name": "Battery"})
        self.write_json(self.manager_deployments / "Unused" / "Unused_federation_input.json", {"name": "Unused"})
        self.write_json(self.federation_input / "strategyInputs" / "stale_federation_input.json", {"name": "stale"})

        staged = staging.stage_federation_inputs_from_deployments()

        self.assertEqual(
            [path.name for path in staged],
            ["PV_federation_input.json", "Battery_federation_input.json"],
        )
        self.assertTrue((self.federation_input / "strategyInputs" / "PV_federation_input.json").is_file())
        self.assertTrue((self.federation_input / "strategyInputs" / "Battery_federation_input.json").is_file())
        self.assertFalse((self.federation_input / "strategyInputs" / "Unused_federation_input.json").exists())
        self.assertFalse((self.federation_input / "strategyInputs" / "stale_federation_input.json").exists())

    def test_stage_federation_inputs_fails_when_required_artifact_is_missing(self) -> None:
        self.write_fedtwin(["PV.production", "Battery.status"])
        self.write_broker_config()
        self.write_json(self.manager_deployments / "PV" / "PV_federation_input.json", {"name": "PV"})

        with self.assertRaises(SystemExit):
            staging.stage_federation_inputs_from_deployments()


if __name__ == "__main__":
    unittest.main()
