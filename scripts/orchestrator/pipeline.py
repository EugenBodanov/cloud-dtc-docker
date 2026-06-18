from __future__ import annotations

from .cli import PipelineOptions
from .docker_compose import run_converter, run_manager_deploy, start_infrastructure
from .pipeline_paths import (
    MANAGER_INPUT_DIR,
    converter_label,
    default_enterprise_architect_export,
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


def run_pipeline(options: PipelineOptions) -> None:
    compose_file = resolve_repo_path(options.compose_file)
    if not compose_file.is_file():
        fail(f"Docker Compose file does not exist: {relative_to_repo(compose_file)}")

    source = (
        resolve_repo_path(options.enterprise_architect_export)
        if options.enterprise_architect_export
        else default_enterprise_architect_export(options.converter)
    )

    print(f"Converter: {converter_label(options.converter)}")
    print(f"Docker Compose file: {relative_to_repo(compose_file)}")
    print(f"Enterprise Architect export: {relative_to_repo(source)}")

    if options.start_infrastructure:
        start_infrastructure(
            options.converter,
            compose_file=compose_file,
            build_images=options.build_images,
            show_container_logs=options.show_container_logs,
        )

    container_input_file, used_model_files = stage_converter_input(
        options.converter,
        source,
        clean_stage=options.clean_stage,
    )
    print_file_listing("used model file(s)", used_model_files)
    if options.converter == "v2":
        print_text_files("sysml-v2 input", used_model_files)

    run_converter(
        options.converter,
        compose_file=compose_file,
        container_input_file=container_input_file,
        digital_twin_name=options.digital_twin_name,
        path_maps=options.path_maps,
        build_images=options.build_images,
        show_container_logs=options.show_container_logs,
    )

    generated_twin_dir = options.generated_twin_dir
    if not generated_twin_dir and options.converter == "v1":
        generated_twin_dir = options.digital_twin_name.lower()

    converter_output = find_converter_output(
        options.converter,
        generated_twin_dir=generated_twin_dir,
    )
    if options.show_output_configs:
        print_config_set("converter output", converter_output)

    saved_credentials = None
    if not options.aws_credentials_file:
        saved_credentials = read_existing_manager_credentials()

    prepare_manager_stage(
        clean_stage=options.clean_stage,
        keep_credentials=saved_credentials,
    )
    copy_configs_to_manager(converter_output, options.aws_credentials_file)

    if options.show_configs:
        print_config_set("digital-twin-manager input", MANAGER_INPUT_DIR)

    if not options.deploy_to_aws:
        print("\nStopped before AWS deploy. Manager configs are ready in " + relative_to_repo(MANAGER_INPUT_DIR))
        return

    run_manager_deploy(
        compose_file=compose_file,
        build_images=options.build_images,
        show_container_logs=options.show_container_logs,
    )
