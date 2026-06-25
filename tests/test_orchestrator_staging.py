from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.grafana_dir = self.pipeline_root / "grafana"
        self.grafana_state = self.grafana_dir / "grafana.json"

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
            "GRAFANA_DIR": staging.GRAFANA_DIR,
            "GRAFANA_STATE_PATH": staging.GRAFANA_STATE_PATH,
        }
        staging.PIPELINE_ROOT = self.pipeline_root
        staging.MANAGER_INPUT_DIR = self.manager_input
        staging.MANAGER_OUTPUT_DIR = self.manager_output
        staging.MANAGER_DEPLOYMENTS_DIR = self.manager_deployments
        staging.FEDERATION_INPUT_DIR = self.federation_input
        staging.FEDERATION_OUTPUT_DIR = self.federation_output
        staging.GRAFANA_DIR = self.grafana_dir
        staging.GRAFANA_STATE_PATH = self.grafana_state

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

    def write_manager_config_set(self, directory: Path, twin_name: str) -> None:
        self.write_json(directory / "config.json", {"digital_twin_name": twin_name})
        self.write_json(directory / "config_hierarchy.json", [])
        self.write_json(directory / "config_iot_devices.json", [])
        self.write_json(directory / "config_events.json", [])

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

    def test_save_manager_deployment_input_copies_current_manager_input(self) -> None:
        self.write_manager_config_set(self.manager_input, "PV")
        self.write_json(self.manager_input / "config_credentials.json", {"aws_region": "eu-central-1"})

        saved_input = staging.save_manager_deployment_input()

        self.assertEqual(saved_input, self.manager_deployments / "PV" / "input")
        self.assertTrue((saved_input / "config.json").is_file())
        self.assertTrue((saved_input / "config_credentials.json").is_file())
        self.assertEqual(staging.list_manager_deployments(), ["PV"])

    def test_save_manager_deployment_output_preserves_saved_input(self) -> None:
        self.write_manager_config_set(self.manager_input, "PV")
        staging.save_manager_deployment_input()
        self.write_json(self.manager_output / "PV_federation_input.json", {"name": "PV"})
        self.write_json(self.manager_output / "Battery_federation_input.json", {"name": "Battery"})
        auth_dir = self.manager_output / "iot_devices_auth"
        auth_dir.mkdir()
        (auth_dir / "device.json").write_text("{}", encoding="utf-8")

        saved_artifact = staging.save_manager_deployment_output()

        self.assertEqual(saved_artifact, self.manager_deployments / "PV" / "output" / "PV_federation_input.json")
        self.assertTrue(saved_artifact.is_file())
        self.assertTrue((self.manager_deployments / "PV" / "input" / "config.json").is_file())
        self.assertTrue((self.manager_deployments / "PV" / "output" / "iot_devices_auth" / "device.json").is_file())
        self.assertFalse((self.manager_deployments / "PV" / "output" / "Battery_federation_input.json").exists())

    def test_save_manager_deployment_input_preserves_existing_output(self) -> None:
        self.write_manager_config_set(self.manager_input, "PV")
        self.write_json(self.manager_deployments / "PV" / "output" / "PV_federation_input.json", {"name": "PV"})

        staging.save_manager_deployment_input()

        self.assertTrue((self.manager_deployments / "PV" / "output" / "PV_federation_input.json").is_file())

    def test_restore_manager_deployment_input_cleans_and_restores_selected_input(self) -> None:
        self.write_manager_config_set(self.manager_deployments / "PV" / "input", "PV")
        self.write_json(self.manager_input / "stale.json", {"stale": True})

        restored_input = staging.restore_manager_deployment_input("pv")

        self.assertEqual(restored_input, self.manager_input)
        self.assertTrue((self.manager_input / "config.json").is_file())
        self.assertFalse((self.manager_input / "stale.json").exists())

    def test_simulator_project_name_is_deterministic_and_safe(self) -> None:
        project_name = staging.simulator_project_name("dtc-y-03")

        self.assertEqual(project_name, staging.simulator_project_name("dtc-y-03"))
        self.assertRegex(project_name, r"^cloud-dtc-simulator-dtc-y-03-[0-9a-f]{8}$")
        self.assertEqual(project_name, project_name.lower())

    def test_simulator_state_can_be_written_read_listed_and_deleted(self) -> None:
        input_dir = self.manager_deployments / "PV" / "input"
        self.write_manager_config_set(input_dir, "PV")

        state = staging.write_simulator_state(
            "PV",
            project_name="cloud-dtc-simulator-pv-12345678",
            host_port=5000,
            input_dir=input_dir,
        )

        self.assertEqual(state["digital_twin_name"], "PV")
        self.assertEqual(state["url"], "http://127.0.0.1:5000")
        self.assertEqual(staging.read_simulator_state("pv")["project_name"], "cloud-dtc-simulator-pv-12345678")
        self.assertEqual([state["digital_twin_name"] for state in staging.list_simulator_states()], ["PV"])

        staging.delete_simulator_state("PV")

        self.assertIsNone(staging.read_simulator_state("PV"))
        self.assertEqual(staging.list_simulator_states(), [])

    def test_list_simulator_states_does_not_require_valid_deployment_input(self) -> None:
        self.write_json(
            self.manager_deployments / "PV" / "simulator.json",
            {
                "digital_twin_name": "PV",
                "project_name": "cloud-dtc-simulator-pv-12345678",
                "host_port": 5000,
                "url": "http://127.0.0.1:5000",
                "input_dir": "pipeline/digital-twin-manager/deployments/PV/input",
            },
        )

        self.assertEqual([state["digital_twin_name"] for state in staging.list_simulator_states()], ["PV"])

    def test_allocate_simulator_host_port_skips_ports_from_state(self) -> None:
        input_dir = self.manager_deployments / "PV" / "input"
        self.write_manager_config_set(input_dir, "PV")
        staging.write_simulator_state(
            "PV",
            project_name="cloud-dtc-simulator-pv-12345678",
            host_port=5000,
            input_dir=input_dir,
        )

        original_port_check = staging._is_local_port_available
        staging._is_local_port_available = lambda port: True
        try:
            self.assertEqual(staging.allocate_simulator_host_port(start=5000, end=5001), 5001)
        finally:
            staging._is_local_port_available = original_port_check

    def test_require_manager_deployment_simulator_input_fails_when_missing(self) -> None:
        with self.assertRaises(SystemExit):
            staging.require_manager_deployment_simulator_input("PV")

    def test_stage_federation_inputs_uses_only_twins_from_fedtwin(self) -> None:
        self.write_fedtwin(["PV.production", "Battery.status"])
        self.write_broker_config()
        self.write_json(self.manager_deployments / "PV" / "output" / "PV_federation_input.json", {"name": "PV"})
        self.write_json(self.manager_deployments / "Battery" / "output" / "Battery_federation_input.json", {"name": "Battery"})
        self.write_json(self.manager_deployments / "Unused" / "output" / "Unused_federation_input.json", {"name": "Unused"})
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
        self.write_json(self.manager_deployments / "PV" / "output" / "PV_federation_input.json", {"name": "PV"})

        with self.assertRaises(SystemExit):
            staging.stage_federation_inputs_from_deployments()

    def test_prepare_local_grafana_stage_writes_runtime_state(self) -> None:
        with patch.dict("os.environ", {"LOCAL_GRAFANA_HOST_PORT": "3030"}, clear=True):
            state = staging.prepare_local_grafana_stage()

        saved_state = json.loads(self.grafana_state.read_text(encoding="utf-8"))
        self.assertEqual(saved_state, state)
        self.assertEqual(state["project_name"], "cloud-dtc-grafana")
        self.assertEqual(state["url"], "http://127.0.0.1:3030")
        self.assertEqual(staging.read_local_grafana_state(), state)


if __name__ == "__main__":
    unittest.main()
