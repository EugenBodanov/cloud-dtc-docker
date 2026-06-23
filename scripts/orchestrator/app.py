from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .cli import LaunchOptions
from .config import PipelineConfig, load_pipeline_config, print_run_config
from .docker_compose import remove_infrastructure, start_infrastructure
from .file_watcher import FileChange, OutputFileWatcher
from .pipeline import (
    remove_cloud_deployer_test_simulator_stage,
    run_digital_twin_manager_destroy_stage,
    run_cloud_deployer_test_simulator_stage,
    run_digital_twin_manager_stage,
    run_federation_stage,
    run_pipeline,
)
from .pipeline_paths import relative_to_repo, resolve_repo_path
from .user_input import UserInput


class StopRequested(Exception):
    pass


def run_app(options: LaunchOptions) -> None:
    config = load_pipeline_config(options.config_file)
    if options.auto_run:
        config = config.with_auto_run(True)
    if options.remove_infrastructure_on_exit:
        config = config.with_remove_infrastructure_on_exit(True)

    compose_file = resolve_repo_path(config.compose_file)
    watch_directory = resolve_repo_path(config.watch.directory)

    print(f"Loaded config: {relative_to_repo(resolve_repo_path(options.config_file))}")
    try:
        start_infrastructure(
            compose_file=compose_file,
            profiles=config.compose_profiles,
            build_images=config.build_images,
            show_container_logs=config.show_container_logs,
        )
        _print_infrastructure_ready()

        watcher = OutputFileWatcher(watch_directory, settle_seconds=config.watch.settle_seconds)
        watcher.reset()

        user_input = UserInput()
        user_input.start()

        print(f"\nWatching {relative_to_repo(watch_directory)} for .xml, .xmi, and .sysml exports.")
        print("Type 'continue digital-twin-manager' to run digital-twin-manager using staged input.")
        print("Type 'destroy digital-twin-manager' to destroy the deployed digital twin.")
        print("Type 'continue fed-sysml' to resume from the fed-sysml step.")
        print("Type 'start simulator' to start cloud-deployer-test-simulator.")
        print("Type 'stop simulator' to stop and remove cloud-deployer-test-simulator.")
        print("Type 'exit' and press Enter to stop.")
        if config.auto_run:
            print("Auto-run is enabled.")
        if config.remove_infrastructure_on_exit:
            print("Infrastructure containers will be removed when the watcher exits.")

        _watch_forever(config, watcher, user_input)
    except StopRequested:
        print("\nStopping run loop.")
    except KeyboardInterrupt:
        print("\nStopping run loop.")
    finally:
        _remove_cloud_deployer_test_simulator_safely(config)
        if config.remove_infrastructure_on_exit:
            remove_infrastructure(
                compose_file=compose_file,
                profiles=config.compose_profiles,
                show_container_logs=config.show_container_logs,
            )
        else:
            print("Infrastructure Docker services remain running.")


def _watch_forever(config: PipelineConfig, watcher: OutputFileWatcher, user_input: UserInput) -> None:
    while True:
        command = user_input.get_line(timeout=config.watch.poll_interval_seconds)
        if command is not None:
            _handle_command(config, command, user_input)

        for change in watcher.poll():
            _handle_file_change(config, change, user_input)


def _handle_file_change(config: PipelineConfig, change: FileChange, user_input: UserInput) -> None:
    print(
        "\nDetected {event_type} export: {path} ({size} bytes, modified {modified})".format(
            event_type=change.event_type,
            path=relative_to_repo(change.path),
            size=change.size,
            modified=datetime.fromtimestamp(change.modified_at).strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    print_run_config(config, source=change.path, converter=change.converter)

    if config.auto_run:
        print("Auto-run accepted this change.")
        run_config = config
        if config.deploy_to_aws is None:
            print("AWS deploy is unset; auto-run will keep deploy disabled.")
            run_config = config.with_deploy_to_aws(False)
        _run_pipeline_safely(run_config, change.path, change.converter)
        return

    if not _prompt_yes_no(user_input, "Run pipeline for this export? [y/N] "):
        print("Skipped pipeline run.")
        return

    run_config = config
    deploy_to_aws = config.deploy_to_aws
    if deploy_to_aws is None:
        deploy_to_aws = _prompt_yes_no(user_input, "Deploy to AWS for this export? [y/N] ")
        run_config = run_config.with_deploy_to_aws(deploy_to_aws)
        print(f"AWS deploy for this run: {'enabled' if deploy_to_aws else 'disabled'}.")

    if deploy_to_aws:
        run_federation = _prompt_yes_no(user_input, "Run federation workflow for this export? [y/N] ")
        run_config = run_config.with_run_federation_workflow(run_federation)
        print(f"Federation workflow for this run: {'enabled' if run_federation else 'disabled'}.")
    elif config.deploy_to_aws is None:
        run_config = run_config.with_run_federation_workflow(False)
    _run_pipeline_safely(run_config, change.path, change.converter)


def _run_pipeline_safely(config: PipelineConfig, source: Path, converter: str) -> None:
    try:
        run_pipeline(config, source=source, converter=converter)
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\nPipeline failed with exit code {code}. Watching will continue.")


def _run_federation_safely(config: PipelineConfig) -> bool:
    try:
        run_federation_stage(config)
        return True
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\nFederation step failed with exit code {code}. Watching will continue.")
        return False


def _run_digital_twin_manager_safely(config: PipelineConfig) -> bool:
    try:
        run_digital_twin_manager_stage(config)
        return True
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\nDigital twin manager step failed with exit code {code}. Watching will continue.")
        return False


def _run_digital_twin_manager_destroy_safely(config: PipelineConfig) -> bool:
    try:
        run_digital_twin_manager_destroy_stage(config)
        return True
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\nDigital twin manager destroy failed with exit code {code}. Watching will continue.")
        return False


def _run_cloud_deployer_test_simulator_safely(config: PipelineConfig) -> bool:
    try:
        run_cloud_deployer_test_simulator_stage(config)
        return True
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\ncloud-deployer-test-simulator failed with exit code {code}. Watching will continue.")
        return False


def _remove_cloud_deployer_test_simulator_safely(config: PipelineConfig) -> bool:
    try:
        remove_cloud_deployer_test_simulator_stage(config)
        return True
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\ncloud-deployer-test-simulator cleanup failed with exit code {code}.")
        return False


def _prompt_yes_no(user_input: UserInput, prompt: str) -> bool:
    print(prompt, end="", flush=True)
    while True:
        line = user_input.get_line(timeout=None)
        if line is None:
            continue
        answer = line.strip().lower()
        if _is_exit(answer):
            raise StopRequested
        if answer in ("", "n", "no"):
            return False
        if answer in ("y", "yes", "run"):
            return True
        print("Please answer 'y', 'n', or 'exit': ", end="", flush=True)


def _handle_command(config: PipelineConfig, command: str, user_input: UserInput) -> None:
    value = command.strip().lower()
    if not value:
        return
    if _is_exit(value):
        raise StopRequested
    if _is_continue_fed_sysml(value):
        print("Continuing from fed-sysml.")
        _run_federation_safely(config)
        return
    if _is_continue_digital_twin_manager(value):
        run_federation = _prompt_yes_no(user_input, "Run federation workflow after digital twin manager? [y/N] ")
        print("Continuing from digital-twin-manager.")
        manager_succeeded = _run_digital_twin_manager_safely(config)
        if run_federation and manager_succeeded:
            _run_federation_safely(config)
        return
    if _is_destroy_digital_twin_manager(value):
        if not _prompt_yes_no(user_input, "Destroy deployed digital twin resources? [y/N] "):
            print("Skipped digital-twin-manager destroy.")
            return
        print("Destroying deployed digital twin with digital-twin-manager.")
        _run_digital_twin_manager_destroy_safely(config)
        return
    if _is_start_cloud_deployer_test_simulator(value):
        print("Starting cloud-deployer-test-simulator.")
        _run_cloud_deployer_test_simulator_safely(config)
        return
    if _is_stop_cloud_deployer_test_simulator(value):
        print("Stopping cloud-deployer-test-simulator.")
        _remove_cloud_deployer_test_simulator_safely(config)
        return

    if value in ("help", "?"):
        _print_commands()
        return
    print("Unknown command. Type 'help' for commands or 'exit' to stop.")


def _is_exit(value: str) -> bool:
    return value in ("exit", "quit", "q")


def _is_continue_fed_sysml(value: str) -> bool:
    tokens = value.replace("-", " ").replace("_", " ").split()
    return tokens in (
        ["fed", "sysml"],
        ["federation"],
        ["continue", "fed", "sysml"],
        ["continue", "with", "fed", "sysml"],
        ["continue", "federation"],
        ["continue", "with", "federation"],
    )


def _is_continue_digital_twin_manager(value: str) -> bool:
    tokens = value.replace("-", " ").replace("_", " ").split()
    return tokens in (
        ["digital", "twin"],
        ["digital", "twin", "manager"],
        ["deploy", "to", "aws"],
        ["continue", "digital", "twin"],
        ["continue", "digital", "twin", "manager"],
        ["continue", "with", "digital", "twin"],
        ["continue", "with", "digital", "twin", "manager"],
        ["continue", "deploy", "to", "aws"],
        ["continue", "with", "deploy", "to", "aws"],
    )


def _is_destroy_digital_twin_manager(value: str) -> bool:
    tokens = value.replace("-", " ").replace("_", " ").split()
    return tokens in (
        ["destroy"],
        ["destroy", "aws"],
        ["destroy", "deploy"],
        ["destroy", "deployment"],
        ["destroy", "digital", "twin"],
        ["destroy", "digital", "twin", "manager"],
        ["digital", "twin", "destroy"],
        ["digital", "twin", "manager", "destroy"],
        ["destroy", "deployed", "digital", "twin"],
        ["destroy", "deployed", "digital", "twin", "manager"],
    )


def _is_start_cloud_deployer_test_simulator(value: str) -> bool:
    tokens = value.replace("-", " ").replace("_", " ").split()
    return tokens in (
        ["simulator"],
        ["test", "simulator"],
        ["cloud", "deployer", "test", "simulator"],
        ["cloud", "deployer", "simulator"],
        ["start", "simulator"],
        ["start", "test", "simulator"],
        ["start", "cloud", "deployer", "test", "simulator"],
        ["run", "simulator"],
        ["run", "test", "simulator"],
        ["run", "cloud", "deployer", "test", "simulator"],
        ["continue", "simulator"],
        ["continue", "test", "simulator"],
        ["continue", "cloud", "deployer", "test", "simulator"],
    )


def _is_stop_cloud_deployer_test_simulator(value: str) -> bool:
    tokens = value.replace("-", " ").replace("_", " ").split()
    return tokens in (
        ["stop", "simulator"],
        ["stop", "test", "simulator"],
        ["stop", "cloud", "deployer", "test", "simulator"],
        ["stop", "cloud", "deployer", "simulator"],
        ["remove", "simulator"],
        ["remove", "test", "simulator"],
        ["remove", "cloud", "deployer", "test", "simulator"],
        ["remove", "cloud", "deployer", "simulator"],
    )


def _print_commands() -> None:
    print("Available commands:")
    print("- continue digital-twin-manager  Run digital-twin-manager using staged manager input.")
    print("- destroy digital-twin-manager   Destroy the deployed digital twin using staged manager input.")
    print("- continue fed-sysml  Resume from the fed-sysml step using staged manager output.")
    print("- start simulator     Start cloud-deployer-test-simulator using staged manager input.")
    print("- stop simulator      Stop and remove cloud-deployer-test-simulator.")
    print("- exit                Stop the watcher.")


def _print_infrastructure_ready() -> None:
    print("\nInfrastructure is up:")
    print("- enterprise-architect: http://127.0.0.1:6080")
    print("- sysml-kernel: service sysml-kernel / container sysml-kernel-container")
