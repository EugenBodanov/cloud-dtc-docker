from __future__ import annotations

from pathlib import Path

from .config import PipelineConfig
from .docker_compose import run_converter, run_manager_deploy
from .pipeline_paths import (
    MANAGER_INPUT_DIR,
    converter_label,
    relative_to_repo,
    resolve_repo_path,
)
from .errors import fail
from .staging import (
    copy_configs_to_manager,
    find_converter_output,
    prepare_manager_stage,
    print_file_listing,
    print_config_set,
    print_text_files,
    read_existing_manager_credentials,
    stage_converter_input,
)


def run_pipeline(config: PipelineConfig, *, source: Path, converter: str) -> None:
    compose_file = resolve_repo_path(config.compose_file)
    if not compose_file.is_file():
        fail(f"Docker Compose file does not exist: {relative_to_repo(compose_file)}")

    source = resolve_repo_path(source)

    print(f"\nConverter: {converter_label(converter)}")
    print(f"Docker Compose file: {relative_to_repo(compose_file)}")
    print(f"Enterprise Architect export: {relative_to_repo(source)}")

    container_input_file, used_model_files = stage_converter_input(
        converter,
        source,
        clean_stage=config.clean_stage,
    )
    print_file_listing("used model file(s)", used_model_files)
    if converter == "v2":
        print_text_files("sysml-v2 input", used_model_files)

    run_converter(
        converter,
        compose_file=compose_file,
        profiles=config.compose_profiles,
        container_input_file=container_input_file,
        digital_twin_name=config.digital_twin_name,
        path_maps=config.path_maps,
        build_images=config.build_images,
        show_container_logs=config.show_container_logs,
    )

    generated_twin_dir = config.generated_twin_dir
    if not generated_twin_dir and converter == "v1":
        generated_twin_dir = config.digital_twin_name.lower()

    converter_output = find_converter_output(
        converter,
        generated_twin_dir=generated_twin_dir,
    )
    if config.show_output_configs:
        print_config_set("converter output", converter_output)

    saved_credentials = None
    if not config.aws_credentials_file:
        saved_credentials = read_existing_manager_credentials()

    prepare_manager_stage(
        clean_stage=config.clean_stage,
        keep_credentials=saved_credentials,
    )
    copy_configs_to_manager(converter_output, config.aws_credentials_file)

    if config.show_configs:
        print_config_set("digital-twin-manager input", MANAGER_INPUT_DIR)

    if not config.deploy_to_aws:
        print("\nStopped before AWS deploy. Manager configs are ready in " + relative_to_repo(MANAGER_INPUT_DIR))
        return

    run_manager_deploy(
        compose_file=compose_file,
        profiles=config.compose_profiles,
        build_images=config.build_images,
        show_container_logs=config.show_container_logs,
    )
