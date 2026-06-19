from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .errors import fail
from .pipeline_paths import (
    DEFAULT_CONFIG_FILE,
    converter_label,
    relative_to_repo,
    resolve_repo_path,
)


@dataclass(frozen=True)
class WatchConfig:
    directory: Path
    poll_interval_seconds: float
    settle_seconds: float


@dataclass(frozen=True)
class PipelineConfig:
    compose_file: Path
    compose_profiles: tuple[str, ...]
    digital_twin_name: str
    generated_twin_dir: str | None
    aws_credentials_file: Path | None
    path_maps: tuple[str, ...]
    build_images: bool
    clean_stage: bool
    show_container_logs: bool
    show_configs: bool
    show_output_configs: bool
    deploy_to_aws: bool
    auto_run: bool
    remove_infrastructure_on_exit: bool
    watch: WatchConfig

    def with_auto_run(self, enabled: bool) -> PipelineConfig:
        return replace(self, auto_run=enabled)

    def with_remove_infrastructure_on_exit(self, enabled: bool) -> PipelineConfig:
        return replace(self, remove_infrastructure_on_exit=enabled)


def load_pipeline_config(config_file: Path = DEFAULT_CONFIG_FILE) -> PipelineConfig:
    config_path = resolve_repo_path(config_file)
    if not config_path.is_file():
        fail(f"Config file does not exist: {relative_to_repo(config_path)}")

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"Config file is not valid JSON: {relative_to_repo(config_path)} ({error})")

    if not isinstance(raw, dict):
        fail("Config file root must be a JSON object.")

    watch_raw = _object(raw.get("watch", {}), "watch")
    return PipelineConfig(
        compose_file=_path(raw, "compose_file", "docker-compose.yaml"),
        compose_profiles=_string_tuple(raw, "compose_profiles"),
        digital_twin_name=_string(raw, "digital_twin_name", "dtwin"),
        generated_twin_dir=_optional_string(raw, "generated_twin_dir"),
        aws_credentials_file=_optional_path(raw, "aws_credentials_file"),
        path_maps=_string_tuple(raw, "path_maps"),
        build_images=_boolean(raw, "build_images", False),
        clean_stage=_boolean(raw, "clean_stage", True),
        show_container_logs=_boolean(raw, "show_container_logs", True),
        show_configs=_boolean(raw, "show_configs", False),
        show_output_configs=_boolean(raw, "show_output_configs", False),
        deploy_to_aws=_boolean(raw, "deploy_to_aws", False),
        auto_run=_boolean(raw, "auto_run", False),
        remove_infrastructure_on_exit=_boolean(raw, "remove_infrastructure_on_exit", False),
        watch=WatchConfig(
            directory=_path(watch_raw, "directory", "enterprise-architect/output"),
            poll_interval_seconds=_positive_float(watch_raw, "poll_interval_seconds", 2.0),
            settle_seconds=_positive_float(watch_raw, "settle_seconds", 1.0),
        ),
    )


def run_config_snapshot(config: PipelineConfig, *, source: Path, converter: str) -> dict[str, Any]:
    return {
        "source": relative_to_repo(source),
        "converter": converter_label(converter),
        "compose_file": relative_to_repo(resolve_repo_path(config.compose_file)),
        "compose_profiles": list(config.compose_profiles),
        "digital_twin_name": config.digital_twin_name,
        "generated_twin_dir": config.generated_twin_dir,
        "aws_credentials_file": _display_optional_path(config.aws_credentials_file),
        "path_maps": list(config.path_maps),
        "build_images": config.build_images,
        "clean_stage": config.clean_stage,
        "show_container_logs": config.show_container_logs,
        "show_configs": config.show_configs,
        "show_output_configs": config.show_output_configs,
        "deploy_to_aws": config.deploy_to_aws,
        "auto_run": config.auto_run,
        "remove_infrastructure_on_exit": config.remove_infrastructure_on_exit,
    }


def print_run_config(config: PipelineConfig, *, source: Path, converter: str) -> None:
    print("\n=== Pipeline run config ===")
    print(json.dumps(run_config_snapshot(config, source=source, converter=converter), indent=2, ensure_ascii=False))


def _display_optional_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return relative_to_repo(resolve_repo_path(path))


def _object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"Config field '{field_name}' must be an object.")
    return value


def _string(raw: dict[str, Any], field_name: str, default: str) -> str:
    value = raw.get(field_name, default)
    if not isinstance(value, str) or not value:
        fail(f"Config field '{field_name}' must be a non-empty string.")
    return value


def _optional_string(raw: dict[str, Any], field_name: str) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        fail(f"Config field '{field_name}' must be null or a non-empty string.")
    return value


def _path(raw: dict[str, Any], field_name: str, default: str) -> Path:
    return Path(_string(raw, field_name, default))


def _optional_path(raw: dict[str, Any], field_name: str) -> Path | None:
    value = _optional_string(raw, field_name)
    return Path(value) if value else None


def _string_tuple(raw: dict[str, Any], field_name: str) -> tuple[str, ...]:
    value = raw.get(field_name, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        fail(f"Config field '{field_name}' must be a list of strings.")
    return tuple(value)


def _boolean(raw: dict[str, Any], field_name: str, default: bool) -> bool:
    value = raw.get(field_name, default)
    if not isinstance(value, bool):
        fail(f"Config field '{field_name}' must be true or false.")
    return value


def _positive_float(raw: dict[str, Any], field_name: str, default: float) -> float:
    value = raw.get(field_name, default)
    if not isinstance(value, (int, float)) or value <= 0:
        fail(f"Config field '{field_name}' must be a positive number.")
    return float(value)
