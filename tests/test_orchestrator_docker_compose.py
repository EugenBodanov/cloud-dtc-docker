from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.orchestrator import docker_compose


class OrchestratorDockerComposeTests(unittest.TestCase):
    def test_manager_actions_are_sent_to_the_interactive_cli(self) -> None:
        runners = {
            "deploy": docker_compose.run_manager_deploy,
            "plan": docker_compose.run_manager_plan,
            "apply": docker_compose.run_manager_apply,
            "destroy": docker_compose.run_manager_destroy,
        }

        for action, runner in runners.items():
            with self.subTest(action=action), patch.object(docker_compose, "run_command") as run_command:
                runner(
                    compose_file=Path("docker-compose.yaml"),
                    profiles=("pipeline",),
                    build_images=False,
                    show_container_logs=True,
                )

                run_command.assert_called_once_with(
                    [
                        "docker",
                        "compose",
                        "-f",
                        "docker-compose.yaml",
                        "--profile",
                        "pipeline",
                        "run",
                        "--rm",
                        "-T",
                        "digital-twin-manager",
                    ],
                    stdin=f"{action}\nexit\n",
                    show_output=True,
                )


if __name__ == "__main__":
    unittest.main()
