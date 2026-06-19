from __future__ import annotations

from pathlib import Path

from .command_runner import run_command
from .errors import fail
from .pipeline_paths import PROFILE_SERVICES, relative_to_repo


def compose_command(compose_file: Path, profiles: tuple[str, ...] = ()) -> list[str]:
    command = ["docker", "compose", "-f", str(compose_file)]
    for profile in profiles:
        command.extend(["--profile", profile])
    return command


def start_infrastructure(
    *,
    compose_file: Path,
    profiles: tuple[str, ...],
    build_images: bool,
    show_container_logs: bool,
) -> None:
    services = ["enterprise-architect", "sysml-kernel"]
    print("\nStarting infrastructure services:")
    for service in services:
        print(f"- {service}")
    print(f"Docker Compose file: {relative_to_repo(compose_file)}")

    command = compose_command(compose_file, profiles) + ["up", "-d"]
    if build_images:
        command.append("--build")
    command.extend(services)
    run_command(command, show_output=show_container_logs)


def run_converter(
    converter: str,
    *,
    compose_file: Path,
    profiles: tuple[str, ...],
    container_input_file: str | None,
    digital_twin_name: str,
    path_maps: tuple[str, ...],
    build_images: bool,
    show_container_logs: bool,
) -> None:
    service = PROFILE_SERVICES[converter]
    command = compose_command(compose_file, profiles) + ["run", "--rm", "-T"]
    if build_images:
        command.append("--build")
    if path_maps:
        command.extend(["-e", "DTP_PATH_MAP=" + ";".join(path_maps)])
    command.append(service)

    if converter == "v1":
        if not container_input_file:
            fail("Internal error: missing SysML v1 input file.")
        command.extend([container_input_file, digital_twin_name])

    run_command(command, show_output=show_container_logs)


def run_manager_deploy(
    *,
    compose_file: Path,
    profiles: tuple[str, ...],
    build_images: bool,
    show_container_logs: bool,
) -> None:
    command = compose_command(compose_file, profiles) + ["run", "--rm", "-T"]
    if build_images:
        command.append("--build")
    command.append("digital-twin-manager")
    run_command(command, stdin="deploy\nexit\n", show_output=show_container_logs)
