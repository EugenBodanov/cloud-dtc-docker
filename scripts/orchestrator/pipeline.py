from __future__ import annotations

from pathlib import Path

from .config import PipelineConfig
from .docker_compose import run_converter, run_manager_deploy, run_fed_sysml
from .pipeline_paths import (
    FEDERATION_OUTPUT_DIR,
    MANAGER_INPUT_DIR,
    MANAGER_OUTPUT_DIR,
    converter_label,
    relative_to_repo,
    resolve_repo_path,
)
from .errors import fail
from .staging import (
    copy_configs_to_manager,
    find_converter_output,
    has_config_set,
    prepare_manager_stage,
    prepare_federation_stage,
    print_file_listing,
    print_config_set,
    print_manager_outputs,
    print_text_files,
    read_existing_manager_credentials,
    stage_converter_input,
    stage_federation_inputs,
)


def run_pipeline(config: PipelineConfig, *, source: Path, converter: str) -> None:
    compose_file = resolve_repo_path(config.compose_file)
    if not compose_file.is_file():
        fail(f"Docker Compose file does not exist: {relative_to_repo(compose_file)}")
    if config.run_federation_workflow and not config.deploy_to_aws:
        fail("run_federation_workflow requires deploy_to_aws=true because fed-sysml uses digital-twin-manager deploy output.")

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

    stage_digital_twin_manager_input(config, converter_output)

    if not config.deploy_to_aws:
        print("\nStopped before AWS deploy. Manager configs are ready in " + relative_to_repo(MANAGER_INPUT_DIR))
        return

    run_digital_twin_manager_stage(config)

    if not config.run_federation_workflow:
        print("\nStopped before federation workflow. Manager output is ready in " + relative_to_repo(MANAGER_OUTPUT_DIR))
        return

    run_federation_stage(config)


def stage_digital_twin_manager_input(config: PipelineConfig, converter_output: Path) -> None:
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


def run_digital_twin_manager_stage(config: PipelineConfig) -> None:
    compose_file = resolve_repo_path(config.compose_file)
    if not compose_file.is_file():
        fail(f"Docker Compose file does not exist: {relative_to_repo(compose_file)}")

    if not has_config_set(MANAGER_INPUT_DIR):
        fail(
            "digital-twin-manager input is missing or incomplete. "
            f"Run the pipeline first so configs are staged in {relative_to_repo(MANAGER_INPUT_DIR)}."
        )

    run_manager_deploy(
        compose_file=compose_file,
        profiles=config.compose_profiles,
        build_images=config.build_images,
        show_container_logs=config.show_container_logs,
    )
    print_manager_outputs()


def run_federation_stage(config: PipelineConfig) -> None:
    compose_file = resolve_repo_path(config.compose_file)
    if not compose_file.is_file():
        fail(f"Docker Compose file does not exist: {relative_to_repo(compose_file)}")

    prepare_federation_stage(clean_stage=config.clean_stage)
    federation_inputs = stage_federation_inputs()
    print_file_listing("fed-sysml strategy input(s)", federation_inputs)

    run_fed_sysml(
        compose_file=compose_file,
        profiles=config.compose_profiles,
        build_images=config.build_images,
        show_container_logs=config.show_container_logs,
    )
    print_file_listing("fed-sysml output", sorted(FEDERATION_OUTPUT_DIR.glob("*")))
