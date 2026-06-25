from __future__ import annotations

import unittest

from scripts.orchestrator import app


class OrchestratorAppCommandTests(unittest.TestCase):
    def test_continue_digital_twin_manager_target_preserves_case(self) -> None:
        matched, target = app._digital_twin_manager_command_target(
            "continue digital-twin-manager PV",
            app.CONTINUE_DIGITAL_TWIN_MANAGER_ALIASES,
        )

        self.assertTrue(matched)
        self.assertEqual(target, "PV")

    def test_destroy_digital_twin_manager_target_preserves_case(self) -> None:
        matched, target = app._digital_twin_manager_command_target(
            "destroy digital-twin-manager Battery",
            app.DESTROY_DIGITAL_TWIN_MANAGER_ALIASES,
        )

        self.assertTrue(matched)
        self.assertEqual(target, "Battery")

    def test_continue_digital_twin_manager_without_target_matches_menu_mode(self) -> None:
        matched, target = app._digital_twin_manager_command_target(
            "continue digital-twin-manager",
            app.CONTINUE_DIGITAL_TWIN_MANAGER_ALIASES,
        )

        self.assertTrue(matched)
        self.assertIsNone(target)

    def test_digital_twin_target_can_contain_hyphens(self) -> None:
        matched, target = app._digital_twin_manager_command_target(
            "continue digital-twin-manager dtc-y-03",
            app.CONTINUE_DIGITAL_TWIN_MANAGER_ALIASES,
        )

        self.assertTrue(matched)
        self.assertEqual(target, "dtc-y-03")

    def test_resolve_manager_deployment_selection_supports_number_and_name(self) -> None:
        deployments = ["Battery", "PV"]

        self.assertEqual(app._resolve_manager_deployment_selection("1", deployments), "Battery")
        self.assertEqual(app._resolve_manager_deployment_selection("pv", deployments), "PV")
        self.assertIsNone(app._resolve_manager_deployment_selection("Unknown", deployments))


if __name__ == "__main__":
    unittest.main()
