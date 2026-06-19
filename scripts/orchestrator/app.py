from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .cli import LaunchOptions
from .config import PipelineConfig, load_pipeline_config, print_run_config
from .docker_compose import start_infrastructure
from .file_watcher import FileChange, OutputFileWatcher
from .pipeline import run_pipeline
from .pipeline_paths import relative_to_repo, resolve_repo_path
from .user_input import UserInput


class StopRequested(Exception):
    pass


def run_app(options: LaunchOptions) -> None:
    config = load_pipeline_config(options.config_file)
    if options.auto_run:
        config = config.with_auto_run(True)

    compose_file = resolve_repo_path(config.compose_file)
    watch_directory = resolve_repo_path(config.watch.directory)

    print(f"Loaded config: {relative_to_repo(resolve_repo_path(options.config_file))}")
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
    print("Type 'exit' and press Enter to stop.")
    if config.auto_run:
        print("Auto-run is enabled.")

    try:
        _watch_forever(config, watcher, user_input)
    except StopRequested:
        print("\nStopping run loop. Docker services remain running.")


def _watch_forever(config: PipelineConfig, watcher: OutputFileWatcher, user_input: UserInput) -> None:
    while True:
        command = user_input.get_line(timeout=config.watch.poll_interval_seconds)
        if command is not None:
            _handle_command(command)

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
        _run_pipeline_safely(config, change.path, change.converter)
        return

    if _prompt_yes_no(user_input, "Run pipeline for this export? [y/N] "):
        _run_pipeline_safely(config, change.path, change.converter)
    else:
        print("Skipped pipeline run.")


def _run_pipeline_safely(config: PipelineConfig, source: Path, converter: str) -> None:
    try:
        run_pipeline(config, source=source, converter=converter)
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        print(f"\nPipeline failed with exit code {code}. Watching will continue.")


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


def _handle_command(command: str) -> None:
    value = command.strip().lower()
    if not value:
        return
    if _is_exit(value):
        raise StopRequested
    print("Unknown command. Type 'exit' to stop.")


def _is_exit(value: str) -> bool:
    return value in ("exit", "quit", "q")


def _print_infrastructure_ready() -> None:
    print("\nInfrastructure is up:")
    print("- enterprise-architect: http://127.0.0.1:6080")
    print("- sysml-kernel: service sysml-kernel / container sysml-kernel-container")
